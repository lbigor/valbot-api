"""
Event-Window Orchestrator.

Nova arquitetura:
  1. Sweep rápido em todos os frames com detectores CPU (barato).
  2. Cada detecção positiva abre uma JANELA TEMPORAL específica
     (antes + depois do evento).
  3. Dentro da janela, o StopDetector mede se houve parada real.
  4. Só então o VLM é acionado com o contexto completo (frames + flag de parada).

Economia esperada:
  - Sem event-windowing: ~25 janelas/min × 7 prompts = 175 calls por 4 min
  - Com event-windowing:  ~3-5 eventos reais × 3-5 prompts = 9-25 calls
  - Redução de ~7-10x no custo de VLM.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import TypedDict

import cv2
import numpy as np

from src.detectors.base import DetectionCandidate, EventType
from src.detectors.crosswalk import CrosswalkDetector
from src.detectors.road_text import RoadTextDetector
from src.detectors.stop_detector import StopDetector, StopEvent
from src.detectors.traffic_light import TrafficLightDetector


@dataclass
class EventWindow:
    event_type: EventType
    trigger_timestamp_s: float
    trigger_confidence: float
    camera: str
    window_start_s: float
    window_end_s: float
    prompts_to_run: list[str]  # quais prompts Tier 1 rodar
    stop_event: StopEvent | None = None
    cross_camera_confirmation: bool = False  # zebra confirmada em BR?
    metadata: dict = field(default_factory=dict)


class _WindowCfg(TypedDict):
    before_s: float
    after_s: float
    prompts: list[str]


# Mapeamento: tipo de evento → janela temporal e prompts a acionar
WINDOW_CONFIG: dict[EventType, _WindowCfg] = {
    EventType.PARE_SIGN: {
        "before_s": 5.0,
        "after_s": 3.0,
        "prompts": ["pare_chao", "linha_retencao"],
    },
    EventType.CROSSWALK: {
        "before_s": 3.0,
        "after_s": 4.0,
        "prompts": ["faixa_pedestre"],  # prompt novo a criar
    },
    EventType.TRAFFIC_LIGHT: {
        "before_s": 3.0,
        "after_s": 2.0,
        "prompts": ["semaforo_vermelho"],
    },
}


class EventOrchestrator:
    def __init__(self, sample_fps: float = 5.0, crosswalk_confirmation_lag_s: float = 3.0):
        """
        Args:
            sample_fps: taxa de amostragem para detectores (5fps = bom custo/benefício)
            crosswalk_confirmation_lag_s: tempo após detecção TL para esperar confirmação BR
        """
        self.sample_fps = sample_fps
        self.crosswalk_lag = crosswalk_confirmation_lag_s

        self.traffic_light_det = TrafficLightDetector()
        self.road_text_det = RoadTextDetector()
        self.crosswalk_tl = CrosswalkDetector(camera="TL")
        self.crosswalk_br = CrosswalkDetector(camera="BR")
        self.stop_det = StopDetector()

    def _iter_frames(self, video_path: Path):
        """Gera (timestamp_s, frame_idx, frame_bgr) amostrado a self.sample_fps."""
        cap = cv2.VideoCapture(str(video_path))
        fps = cap.get(cv2.CAP_PROP_FPS)
        step = max(1, int(fps / self.sample_fps))
        idx = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if idx % step == 0:
                yield idx / fps, idx, frame
            idx += 1
        cap.release()

    @staticmethod
    def _split_quadrants(frame: np.ndarray) -> dict[str, np.ndarray]:
        h, w = frame.shape[:2]
        hh, hw = h // 2, w // 2
        return {
            "TL": frame[:hh, :hw],
            "TR": frame[:hh, hw:],
            "BL": frame[hh:, :hw],
            "BR": frame[hh:, hw:],
        }

    def _merge_nearby_detections(
        self, detections: list[DetectionCandidate], same_event_merge_window_s: float = 2.5
    ) -> list[DetectionCandidate]:
        """
        Agrupa detecções contíguas do mesmo tipo dentro de uma janela curta.
        Isto evita gerar múltiplas janelas para um mesmo evento "ondulante".
        Mantém a detecção com maior confidence do grupo.
        """
        if not detections:
            return []
        detections = sorted(detections, key=lambda d: (d.event_type, d.timestamp_s))
        merged = [detections[0]]
        for d in detections[1:]:
            last = merged[-1]
            same_type = d.event_type == last.event_type
            close_in_time = (d.timestamp_s - last.timestamp_s) < same_event_merge_window_s
            if same_type and close_in_time:
                if d.confidence > last.confidence:
                    merged[-1] = d
            else:
                merged.append(d)
        return merged

    def sweep(self, video_path: Path) -> list[DetectionCandidate]:
        """Passada única de detectores em todos os frames amostrados."""
        all_detections: list[DetectionCandidate] = []

        for ts, idx, frame in self._iter_frames(video_path):
            quads = self._split_quadrants(frame)

            # traffic light — frontal
            d = self.traffic_light_det.detect(quads["TL"], idx, ts)
            if d.should_trigger_vlm:
                all_detections.append(d)

            # road text (PARE, DIREIÇÃO, etc.) — frontal
            d = self.road_text_det.detect(quads["TL"], idx, ts)
            if d.should_trigger_vlm:
                all_detections.append(d)

            # crosswalk — frontal e traseira (em paralelo)
            d_tl = self.crosswalk_tl.detect(quads["TL"], idx, ts)
            if d_tl.should_trigger_vlm:
                all_detections.append(d_tl)
            d_br = self.crosswalk_br.detect(quads["BR"], idx, ts)
            if d_br.should_trigger_vlm:
                all_detections.append(d_br)

        return self._merge_nearby_detections(all_detections)

    def build_windows(
        self, detections: list[DetectionCandidate], video_duration_s: float
    ) -> list[EventWindow]:
        """Converte detecções em janelas temporais com contexto."""
        windows: list[EventWindow] = []

        # agrupa detecções de crosswalk por TL/BR para cross-confirmation
        [d for d in detections if d.event_type == EventType.CROSSWALK and d.camera == "TL"]
        br_crosswalks = [
            d for d in detections if d.event_type == EventType.CROSSWALK and d.camera == "BR"
        ]

        for d in detections:
            if d.event_type == EventType.CROSSWALK and d.camera == "BR":
                continue  # BR só é confirmação, não gera janela própria

            cfg = WINDOW_CONFIG.get(d.event_type)
            if not cfg:
                continue

            w = EventWindow(
                event_type=d.event_type,
                trigger_timestamp_s=d.timestamp_s,
                trigger_confidence=d.confidence,
                camera=d.camera,
                window_start_s=max(0.0, d.timestamp_s - cfg["before_s"]),
                window_end_s=min(video_duration_s, d.timestamp_s + cfg["after_s"]),
                prompts_to_run=list(cfg["prompts"]),
                metadata={**d.metadata, "trigger_bbox": d.bbox},
            )

            # cross-camera confirmation para zebra
            if d.event_type == EventType.CROSSWALK and d.camera == "TL":
                for br in br_crosswalks:
                    lag = br.timestamp_s - d.timestamp_s
                    if 0.5 <= lag <= self.crosswalk_lag + 2.0:
                        w.cross_camera_confirmation = True
                        w.metadata["br_confirmation_ts"] = br.timestamp_s
                        w.metadata["br_confidence"] = br.confidence
                        break

            windows.append(w)

        return windows

    def enrich_with_stop_detection(
        self, windows: list[EventWindow], video_path: Path
    ) -> list[EventWindow]:
        """Para cada janela, amostra frames densos e mede se houve parada."""
        cap = cv2.VideoCapture(str(video_path))
        cap.get(cv2.CAP_PROP_FPS)
        for w in windows:
            frames = []
            ts_list = []
            # amostra a 4fps dentro da janela (frames densos para stop detect)
            ts = w.window_start_s
            while ts < w.window_end_s:
                cap.set(cv2.CAP_PROP_POS_MSEC, ts * 1000)
                ok, frame = cap.read()
                if ok:
                    quads = self._split_quadrants(frame)
                    frames.append(quads["TL"])  # frontal para medir movimento
                    ts_list.append(ts)
                ts += 0.25
            if len(frames) >= 2:
                w.stop_event = self.stop_det.is_stopped_in_window(frames, ts_list)
        cap.release()
        return windows

    def summary(self, windows: list[EventWindow]) -> dict:
        by_type: dict[str, int] = {}
        with_stop: dict[str, int] = {}
        for w in windows:
            by_type[w.event_type.value] = by_type.get(w.event_type.value, 0) + 1
            if w.stop_event:
                with_stop[w.event_type.value] = with_stop.get(w.event_type.value, 0) + 1
        return {
            "total_windows": len(windows),
            "by_event_type": by_type,
            "windows_with_stop_detected": with_stop,
            "estimated_vlm_calls": sum(len(w.prompts_to_run) for w in windows),
        }
