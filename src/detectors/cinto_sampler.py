"""
Cinto Sampler — protocolo de amostragem para R1020-GR-f.

Estratégia (memory feedback_cinto_estrategia, 2026-04-25):
    Fase 1: 5 frames fixos da câmera INTERNA (BL) em 0%, 25%, 50%, 75%, 100%.
    Fase 2: se 5/5 inconclusivos por contraste insuficiente, dividir vídeo em
            3 terços e sortear 1 frame por terço. Repetir até max_retries.

Decisão por frame (schema rígido):
    {
      "torso_visivel": bool,
      "contraste_suficiente": bool,
      "cinto_visivel": true|false|null,
      "confidence": 0.0-1.0,
      "evidence": "<=15 palavras"
    }

Veredito final:
    - APROVADO        — ≥1 frame com cinto_visivel=true E confidence ≥0.7
    - DETECTADO       — ≥1 frame com cinto_visivel=false E confidence ≥0.7
    - INCONCLUSIVO    — esgotou retries sem decisão clara
    - PENDENTE_REVISAO_HUMANA — sem callback VLM (modo offline)

VLM é fornecido via callback opcional. Sem callback, o sampler apenas
extrai e salva frames para revisão humana posterior (modo MVP atual).
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np

from src.ingestion.grid_slicer import GridSlicer

VlmCallback = Callable[[np.ndarray, str], dict]


@dataclass
class CintoFrame:
    fase: str
    pos_pct: float
    timestamp_s: float
    frame_idx: int
    image_path: str
    vlm_decision: dict | None = None


@dataclass
class CintoVerdict:
    veredito: str
    confianca: float
    motivo: str
    frames: list[CintoFrame]
    rondadas_retry: int = 0
    sanity_check_examinador: bool | None = None


CONF_THRESHOLD = 0.7


def _seek_frame(video_path: Path, target_ts: float) -> tuple[np.ndarray | None, int, float]:
    """Lê 1 frame no timestamp aproximado. Retorna (frame_grid, frame_idx, ts_real)."""
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    target_idx = min(total - 1, max(0, round(target_ts * fps)))
    cap.set(cv2.CAP_PROP_POS_FRAMES, target_idx)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        return None, target_idx, target_idx / fps
    return frame, target_idx, target_idx / fps


def _extract_interna(grid_frame: np.ndarray, slicer: GridSlicer | None = None) -> np.ndarray:
    """Recorta o quadrante da câmera INTERNA do grid 2x2.

    Se `slicer` é fornecido, usa o layout detectado (VIP Intelbras: BL,
    Hikvision: TL). Sem slicer, mantém comportamento legado (BL).
    """
    if slicer is not None:
        return slicer.extract_camera(grid_frame, "interna")
    h, w = grid_frame.shape[:2]
    return grid_frame[h // 2 :, : w // 2]


def amostrar_cinto(
    video_path: Path,
    output_dir: Path,
    vlm_callback: VlmCallback | None = None,
    max_retries: int = 3,
    seed: int | str | None = None,
) -> CintoVerdict:
    """
    Amostra frames do vídeo para avaliação de cinto.

    Args:
        video_path: caminho do vídeo grid 2x2.
        output_dir: pasta para salvar frames extraídos. Será criada.
        vlm_callback: função(image_bgr, prompt) -> dict com schema da decisão.
                      None = modo offline (extrai e marca pendente_revisao_humana).
        max_retries: número máximo de rodadas de retry (cada uma = 3 frames).
        seed: semente p/ reprodutibilidade do retry. Default = nome do vídeo.

    Returns:
        CintoVerdict com veredito, confiança, frames extraídos.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    slicer = GridSlicer(video_path)
    duration = slicer.duration_s
    if duration <= 0:
        return CintoVerdict(
            veredito="inconclusivo",
            confianca=0.0,
            motivo="duração inválida",
            frames=[],
        )

    rng = random.Random(seed if seed is not None else str(video_path.name))  # noqa: S311  # amostragem reprodutivel, nao crypto

    # ---- Fase 1: 5 frames fixos
    frames: list[CintoFrame] = []
    fixed_pcts = [0.0, 0.25, 0.50, 0.75, 1.0]
    for pct in fixed_pcts:
        ts = pct * duration
        # evita ts == duration exato (último frame pode falhar)
        if pct >= 1.0:
            ts = max(0.0, duration - 0.5)
        cf = _processar_frame(
            video_path,
            ts,
            output_dir,
            fase="fixed",
            pos_pct=pct,
            vlm_callback=vlm_callback,
            slicer=slicer,
        )
        if cf is not None:
            frames.append(cf)

    # ---- Avalia: alguma decisão clara?
    if vlm_callback is None:
        return CintoVerdict(
            veredito="pendente_revisao_humana",
            confianca=0.0,
            motivo="sem callback VLM; frames extraídos para revisão",
            frames=frames,
        )

    veredito = _veredito_final(frames)
    if veredito[0] in ("aprovado", "detectado"):
        return CintoVerdict(
            veredito=veredito[0],
            confianca=veredito[1],
            motivo=veredito[2],
            frames=frames,
        )

    # ---- Fase 2: retry adaptativo (3 terços × max_retries rondas)
    rondadas = 0
    for r in range(1, max_retries + 1):
        rondadas = r
        for terco_idx in range(3):
            t_min = terco_idx * duration / 3
            t_max = (terco_idx + 1) * duration / 3
            ts = rng.uniform(t_min, t_max)
            cf = _processar_frame(
                video_path,
                ts,
                output_dir,
                fase=f"retry_{r}",
                pos_pct=ts / duration,
                vlm_callback=vlm_callback,
                slicer=slicer,
            )
            if cf is not None:
                frames.append(cf)

        veredito = _veredito_final(frames)
        if veredito[0] in ("aprovado", "detectado"):
            return CintoVerdict(
                veredito=veredito[0],
                confianca=veredito[1],
                motivo=veredito[2],
                frames=frames,
                rondadas_retry=rondadas,
            )

    return CintoVerdict(
        veredito="inconclusivo",
        confianca=0.0,
        motivo=f"esgotou {max_retries} rondas de retry sem frame conclusivo",
        frames=frames,
        rondadas_retry=rondadas,
    )


def _processar_frame(
    video_path: Path,
    target_ts: float,
    output_dir: Path,
    fase: str,
    pos_pct: float,
    vlm_callback: VlmCallback | None,
    slicer: GridSlicer | None = None,
) -> CintoFrame | None:
    grid, frame_idx, ts_real = _seek_frame(video_path, target_ts)
    if grid is None:
        return None
    interna = _extract_interna(grid, slicer)
    fname = f"{fase}_{frame_idx:06d}.jpg"
    img_path = output_dir / fname
    cv2.imwrite(str(img_path), interna, [cv2.IMWRITE_JPEG_QUALITY, 85])

    decision = None
    if vlm_callback is not None:
        prompt = (
            "Você é examinador DETRAN avaliando R1020-GR-f (cinto). "
            "Analise o frame da câmera INTERNA. O CONDUTOR está à DIREITA. "
            "Responda em JSON com: torso_visivel, contraste_suficiente, "
            "cinto_visivel (true|false|null), confidence (0..1), "
            "evidence (≤15 palavras)."
        )
        try:
            decision = vlm_callback(interna, prompt)
        except Exception as e:
            decision = {
                "error": str(e),
                "cinto_visivel": None,
                "confidence": 0.0,
                "torso_visivel": False,
                "contraste_suficiente": False,
                "evidence": "callback falhou",
            }

    return CintoFrame(
        fase=fase,
        pos_pct=round(pos_pct, 4),
        timestamp_s=round(ts_real, 2),
        frame_idx=frame_idx,
        image_path=str(img_path.relative_to(output_dir.parent))
        if output_dir.parent in img_path.parents
        else str(img_path),
        vlm_decision=decision,
    )


def _veredito_final(frames: list[CintoFrame]) -> tuple[str, float, str]:
    """Decide com base nas decisões VLM acumuladas. Retorna (veredito, conf, motivo)."""
    melhor_pos = (0.0, "")  # (conf, motivo)
    melhor_neg = (0.0, "")
    for f in frames:
        d = f.vlm_decision or {}
        cv_ = d.get("cinto_visivel")
        conf = float(d.get("confidence") or 0.0)
        if cv_ is True and conf >= CONF_THRESHOLD and conf > melhor_pos[0]:
            melhor_pos = (conf, f"frame {f.frame_idx} ({f.fase}): {d.get('evidence', '')}")
        elif cv_ is False and conf >= CONF_THRESHOLD and conf > melhor_neg[0]:
            melhor_neg = (conf, f"frame {f.frame_idx} ({f.fase}): {d.get('evidence', '')}")
    if melhor_pos[0] > 0:
        return ("aprovado", melhor_pos[0], melhor_pos[1])
    if melhor_neg[0] > 0:
        return ("detectado", melhor_neg[0], melhor_neg[1])
    return ("inconclusivo", 0.0, "nenhum frame com confidence ≥0.7")


def verdict_to_dict(v: CintoVerdict) -> dict:
    return {
        "veredito": v.veredito,
        "confianca": round(v.confianca, 3),
        "motivo": v.motivo,
        "rondadas_retry": v.rondadas_retry,
        "sanity_check_examinador": v.sanity_check_examinador,
        "frames": [asdict(f) for f in v.frames],
    }
