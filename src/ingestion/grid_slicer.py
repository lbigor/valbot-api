"""
Grid Slicer — separa vídeo 2x2 em 4 streams de câmera independentes.

Layout confirmado VIP Intelbras (validado com vídeos reais):
    +----------------+----------------+
    |    FRONTAL     | LATERAL_DIR    |  (superior)
    +----------------+----------------+
    |    INTERNA     | TRAS/LAT_ESQ   |  (inferior)
    +----------------+----------------+

Decisão de design: em vez de gerar 4 arquivos de vídeo (caro em I/O),
expomos um iterator que devolve 4 sub-frames sincronizados por timestamp.
"""

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

import cv2
import numpy as np

log = logging.getLogger(__name__)
_OCR_READER = None


@dataclass
class CameraFrame:
    """Frame de uma câmera específica num timestamp específico."""

    camera: str
    timestamp_s: float
    frame_idx: int
    image: np.ndarray


@dataclass
class GridFrame:
    """Conjunto sincronizado de 4 frames no mesmo instante."""

    timestamp_s: float
    frame_idx: int
    frontal: np.ndarray  # TL
    lateral_direita: np.ndarray  # TR
    interna: np.ndarray  # BL
    traseira_esq: np.ndarray  # BR

    def as_list(self) -> list[CameraFrame]:
        return [
            CameraFrame("frontal", self.timestamp_s, self.frame_idx, self.frontal),
            CameraFrame("lateral_direita", self.timestamp_s, self.frame_idx, self.lateral_direita),
            CameraFrame("interna", self.timestamp_s, self.frame_idx, self.interna),
            CameraFrame("traseira_esq", self.timestamp_s, self.frame_idx, self.traseira_esq),
        ]


def detect_layout(video_path: Path, default: str = "vip_intelbras") -> str:
    """
    Detecta o layout do gravador via marca d'água (OCR easyocr nos 4
    quadrantes do frame ~10s do vídeo).

    Devolve "vip_intelbras", "hikvision" ou o `default` se nada bater.
    Auto-detecção custa ~1-2s por vídeo (lazy import do easyocr).
    """
    video_path = Path(video_path)
    if not video_path.exists():
        return default
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(min(fps * 10, 50)))
    ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        return default
    try:
        import easyocr

        # reader compartilhado se já existe
        global _OCR_READER
        if _OCR_READER is None:
            _OCR_READER = easyocr.Reader(["pt", "en"], gpu=False, verbose=False)
        # OCR no frame inteiro (640x720 ÷ 2x2 já são quadrantes pequenos)
        results = _OCR_READER.readtext(frame, detail=0, paragraph=False)
        joined = " ".join(str(r).lower() for r in results)
        if "hikvision" in joined or "hk vision" in joined:
            return "hikvision"
        if "intelbras" in joined or "vip intel" in joined:
            return "vip_intelbras"
    except Exception as e:
        log.debug(
            "grid_slicer.detect_layout falhou em %s: %s — usando default %s", video_path, e, default
        )
    return default


class GridSlicer:
    """
    Fatia vídeos em grid 2x2. Layout configurável para diferentes fabricantes
    de DVR (VIP Intelbras é o padrão atual).
    """

    # Layout VIP Intelbras confirmado com vídeos reais (1.mp4-4.mp4)
    LAYOUT_VIP_INTELBRAS: ClassVar[dict[str, str]] = {
        "TL": "frontal",
        "TR": "lateral_direita",
        "BL": "interna",
        "BR": "traseira_esq",
    }

    # Layout Hikvision confirmado com os 5 vídeos TREINO IA (Apr/2026)
    # — câmera interna fica em TL, frontal em TR. Diferente do VIP Intelbras.
    LAYOUT_HIKVISION: ClassVar[dict[str, str]] = {
        "TL": "interna",
        "TR": "frontal",
        "BL": "traseira_esq",
        "BR": "lateral_direita",
    }

    LAYOUTS_BY_NAME: ClassVar[dict[str, dict[str, str]]] = {
        "vip_intelbras": LAYOUT_VIP_INTELBRAS,
        "hikvision": LAYOUT_HIKVISION,
    }

    def __init__(
        self, video_path: Path, layout: dict[str, str] | None = None, sample_fps: float = 1.0
    ):
        self.video_path = Path(video_path)
        if layout is None:
            # auto-detecção via OCR da marca d'água
            name = detect_layout(self.video_path)
            self.layout_name = name
            self.layout = self.LAYOUTS_BY_NAME.get(name, self.LAYOUT_VIP_INTELBRAS)
        else:
            self.layout = layout
            self.layout_name = next(
                (n for n, m in self.LAYOUTS_BY_NAME.items() if m == layout),
                "custom",
            )
        self.sample_fps = sample_fps

        if not self.video_path.exists():
            raise FileNotFoundError(f"Vídeo não encontrado: {self.video_path}")

        cap = cv2.VideoCapture(str(self.video_path))
        self.fps = cap.get(cv2.CAP_PROP_FPS)
        self.width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.duration_s = self.total_frames / self.fps if self.fps > 0 else 0
        cap.release()

        if self.width == 0 or self.height == 0:
            raise ValueError(f"Não foi possível ler dimensões de {self.video_path}")

        self.half_w = self.width // 2
        self.half_h = self.height // 2

    def _split_quadrants(self, frame: np.ndarray) -> dict[str, np.ndarray]:
        return {
            "TL": frame[: self.half_h, : self.half_w],
            "TR": frame[: self.half_h, self.half_w :],
            "BL": frame[self.half_h :, : self.half_w],
            "BR": frame[self.half_h :, self.half_w :],
        }

    def quadrant_for(self, camera: str) -> str:
        """Devolve o código do quadrante (TL/TR/BL/BR) que serve `camera`."""
        for q, c in self.layout.items():
            if c == camera:
                return q
        raise KeyError(f"layout {self.layout} não tem câmera '{camera}'")

    def extract_camera(self, frame: np.ndarray, camera: str) -> np.ndarray:
        """Recorta direto a câmera desejada do frame grid 2x2."""
        return self._split_quadrants(frame)[self.quadrant_for(camera)]

    def iter_frames(self) -> Iterator[GridFrame]:
        cap = cv2.VideoCapture(str(self.video_path))
        step = max(1, int(self.fps / self.sample_fps)) if self.sample_fps > 0 else 1

        frame_idx = 0
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_idx % step == 0:
                    quads = self._split_quadrants(frame)
                    cameras = {self.layout[q]: img for q, img in quads.items()}
                    yield GridFrame(
                        timestamp_s=frame_idx / self.fps,
                        frame_idx=frame_idx,
                        frontal=cameras["frontal"],
                        lateral_direita=cameras["lateral_direita"],
                        interna=cameras["interna"],
                        traseira_esq=cameras["traseira_esq"],
                    )
                frame_idx += 1
        finally:
            cap.release()

    def metadata(self) -> dict:
        return {
            "path": str(self.video_path),
            "fps": self.fps,
            "width": self.width,
            "height": self.height,
            "total_frames": self.total_frames,
            "duration_s": round(self.duration_s, 2),
            "layout": self.layout,
            "sample_fps": self.sample_fps,
        }
