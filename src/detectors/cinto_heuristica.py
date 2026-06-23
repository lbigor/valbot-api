"""
Heurística determinística para R1020-GR-f: detecta faixa diagonal escura
sobre o torso do CONDUTOR (lado direito do quadrante BL).

Algoritmo:
    1. Recorta torso a partir do bbox de pose (ombros direito + esquerdo +
       quadril estimado). Se não houver pose, usa região fixa heurística
       (lado direito do BL, 30%-100% horizontal · 30%-90% vertical).
    2. Converte pra HSV e gera mask de pixels ESCUROS (V baixo).
    3. Aplica detecção de linhas diagonal via Hough sobre o mask + Canny.
    4. Score = (área_escura/área_torso) × (linhas_diagonais_detectadas) × confiança.
    5. Decisão:
        score >= 0.45 → cinto_visivel=True com conf=0.75
        score <= 0.10 → cinto_visivel=False com conf=0.65
        else          → cinto_visivel=None (mantém pendente revisão humana)

A heurística é conservadora: prefere "inconclusivo" do que falso positivo.
Uma jaqueta preta zipada sem cinto também pode dar score alto — por isso
o threshold é alto e o teste de diagonalidade filtra isso (jaqueta preta
gera contraste uniforme, não linha).
"""

from __future__ import annotations

import contextlib
import logging
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

log = logging.getLogger(__name__)


@dataclass
class HeuristicaDecisao:
    cinto_visivel: bool | None  # True/False/None
    confidence: float  # 0..1
    score: float  # bruto
    contraste_suficiente: bool
    torso_visivel: bool
    evidence: str
    debug: dict


def _torso_box_from_pose(person: dict, w: int, h: int) -> tuple[int, int, int, int] | None:
    """Deriva bbox do torso a partir dos keypoints (ombros + quadril)."""
    kpts = person.get("kpts", {})
    pts = []
    for k in ("left_shoulder", "right_shoulder", "left_hip", "right_hip"):
        kp = kpts.get(k)
        if kp and len(kp) >= 3 and kp[2] >= 0.25:
            pts.append((kp[0], kp[1]))
    if len(pts) < 2:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    pad = 10
    x1 = max(0, int(min(xs) - pad))
    y1 = max(0, int(min(ys) - pad))
    x2 = min(w, int(max(xs) + pad))
    y2 = min(h, int(max(ys) + pad * 3))  # estende pra baixo se quadril fraco
    if x2 - x1 < 30 or y2 - y1 < 30:
        return None
    return (x1, y1, x2, y2)


def _torso_box_fallback(w: int, h: int) -> tuple[int, int, int, int]:
    """Região conservadora: lado direito do BL onde o condutor sempre fica."""
    return (int(w * 0.35), int(h * 0.25), int(w * 0.85), int(h * 0.85))


# Sanity check: lazy load do YOLO pose pra detectar pessoas no frame.
# Se a câmera está olhando paisagem (não interior), nenhuma pessoa aparece e
# devemos NUNCA aprovar cinto. Evita o caso histórico de aprovar cinto em
# imagem de rua só por achar "linhas diagonais escuras" (postes, calçada).
_POSE_MODEL_SANITY = None


def _detectar_pessoas(image_bgr: np.ndarray) -> list[dict]:
    """Roda YOLO pose no frame e devolve persons detectadas.

    Custo: ~50-100ms por frame em CPU. Cacheia o modelo entre chamadas.
    Retorna [] se ultralytics não estiver disponível (degradação graciosa).
    """
    global _POSE_MODEL_SANITY
    try:
        if _POSE_MODEL_SANITY is None:
            from pathlib import Path

            from ultralytics import YOLO

            model_path = Path(__file__).resolve().parents[2] / "yolo11s-pose.pt"
            if not model_path.exists():
                return []
            _POSE_MODEL_SANITY = YOLO(str(model_path))
        result = _POSE_MODEL_SANITY(image_bgr, conf=0.3, verbose=False)[0]
        if result.boxes is None or len(result.boxes) == 0:
            return []
        out = []
        for i in range(len(result.boxes)):
            xyxy = result.boxes.xyxy[i].cpu().numpy().tolist()
            conf = float(result.boxes.conf[i].item())
            kpts_arr = (
                result.keypoints.data[i].cpu().numpy() if result.keypoints is not None else None
            )
            kpts = {}
            if kpts_arr is not None:
                names = [
                    "nose",
                    "left_eye",
                    "right_eye",
                    "left_ear",
                    "right_ear",
                    "left_shoulder",
                    "right_shoulder",
                    "left_elbow",
                    "right_elbow",
                    "left_wrist",
                    "right_wrist",
                    "left_hip",
                    "right_hip",
                    "left_knee",
                    "right_knee",
                    "left_ankle",
                    "right_ankle",
                ]
                for j, name in enumerate(names):
                    if j < len(kpts_arr):
                        x, y, c = kpts_arr[j].tolist()
                        kpts[name] = [x, y, c]
            out.append({"bbox": xyxy, "confidence": conf, "kpts": kpts})
        return out
    except Exception:
        return []


def _load_config() -> dict:
    """Carrega config.json (ajustado pela UI Configurações). Defaults seguros."""
    import json

    path = Path(__file__).resolve().parents[2] / "storage" / "training" / "config.json"
    defaults = {
        "cinto_threshold_diagonais": 2,
        "cinto_dark_ratio_min": 0.15,
        "cinto_dark_ratio_max": 0.65,
    }
    if path.exists():
        try:
            return {**defaults, **json.loads(path.read_text())}
        except (json.JSONDecodeError, OSError) as e:
            log.warning("cinto_heuristica config invalido em %s: %s — usando defaults", path, e)
    return defaults


def avaliar_frame(
    bl_image: np.ndarray,
    pose_persons: list[dict] | None = None,
) -> HeuristicaDecisao:
    """
    bl_image: BGR do quadrante BL (640×360 típico).
    pose_persons: persons do entry de pose mais próximo no tempo (opcional).
    """
    cfg = _load_config()
    min_diag = int(cfg.get("cinto_threshold_diagonais", 2))
    dark_min = float(cfg.get("cinto_dark_ratio_min", 0.15))
    dark_max = float(cfg.get("cinto_dark_ratio_max", 0.65))
    h, w = bl_image.shape[:2]
    debug: dict = {}

    # Identifica torso do CONDUTOR (right-side person)
    torso_box = None
    if pose_persons:
        condutor = next((p for p in pose_persons if p.get("role") == "CONDUTOR"), None)
        if condutor:
            torso_box = _torso_box_from_pose(condutor, w, h)
            debug["torso_source"] = "pose_condutor"

    # Sanity check: se não veio pose externo, roda YOLO pose no frame.
    # Sem nenhuma pessoa visível = câmera errada (paisagem) ou frame ruim.
    # Nunca podemos APROVAR cinto sem ver alguém.
    if torso_box is None:
        ad_hoc_persons = _detectar_pessoas(bl_image)
        debug["sanity_check_persons"] = len(ad_hoc_persons)
        if not ad_hoc_persons:
            return HeuristicaDecisao(
                cinto_visivel=None,
                confidence=0.0,
                score=0.0,
                contraste_suficiente=False,
                torso_visivel=False,
                evidence="nenhuma pessoa detectada na cena — câmera errada ou frame ruim",
                debug=debug,
            )
        # Pega pessoa mais à direita (condutor típico) com torso visível
        ad_hoc_persons.sort(key=lambda p: -((p["bbox"][0] + p["bbox"][2]) / 2))
        for p in ad_hoc_persons:
            tb = _torso_box_from_pose(p, w, h)
            if tb is not None:
                torso_box = tb
                debug["torso_source"] = "sanity_check_pose"
                break
        if torso_box is None:
            torso_box = _torso_box_fallback(w, h)
            debug["torso_source"] = "fallback_region_after_sanity"

    x1, y1, x2, y2 = torso_box
    torso = bl_image[y1:y2, x1:x2]
    debug["torso_bbox"] = list(torso_box)
    debug["torso_size"] = [torso.shape[1], torso.shape[0]]

    if torso.size == 0:
        return HeuristicaDecisao(
            cinto_visivel=None,
            confidence=0.0,
            score=0.0,
            contraste_suficiente=False,
            torso_visivel=False,
            evidence="torso vazio",
            debug=debug,
        )

    # 1. mascarar pixels ESCUROS (V<60 em HSV)
    hsv = cv2.cvtColor(torso, cv2.COLOR_BGR2HSV)
    v = hsv[:, :, 2]
    dark = (v < 60).astype(np.uint8) * 255
    dark_ratio = float(dark.sum() / 255) / float(torso.shape[0] * torso.shape[1])
    debug["dark_ratio"] = round(dark_ratio, 3)

    # 2. avalia se há contraste (não é tudo escuro nem tudo claro)
    contraste_suficiente = 0.05 < dark_ratio < 0.65
    debug["contraste_suficiente"] = contraste_suficiente

    # 3. detecção de linha diagonal via Canny + HoughLinesP
    gray = cv2.cvtColor(torso, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=25,
        minLineLength=int(min(torso.shape[:2]) * 0.4),
        maxLineGap=10,
    )
    diag_count = 0
    if lines is not None:
        for line in lines:
            x1l, y1l, x2l, y2l = line[0]
            dx = x2l - x1l
            dy = y2l - y1l
            length = np.hypot(dx, dy)
            if length < 20:
                continue
            angle = abs(np.degrees(np.arctan2(dy, dx)))
            # Diagonais entre 25° e 65° (cinto cruza torso)
            if 25 <= angle <= 65 or 115 <= angle <= 155:
                diag_count += 1
    debug["diagonals"] = int(diag_count)

    # 4. score = presença de diagonal (cinto cruzando torso)
    diag_factor = min(1.0, diag_count / 3.0)
    debug["score"] = round(diag_factor, 3)
    score = diag_factor

    # 5. Decisão CONSERVADORA — falsos positivos custam mais que falsos negativos.
    #    Reprovar quem tem cinto = injustiça grave; passar quem está sem cinto
    #    será pego pela revisão humana. Filosofia: heurística só decide quando
    #    a evidência é INEQUÍVOCA.

    # 5a. Cinto PRESENTE: ≥N diagonais E contraste razoável (limites configuráveis)
    if diag_count >= min_diag and dark_min <= dark_ratio <= dark_max:
        return HeuristicaDecisao(
            cinto_visivel=True,
            confidence=0.75,
            score=score,
            contraste_suficiente=True,
            torso_visivel=True,
            evidence=f"diagonal escura sobre torso · {diag_count} linhas · dark_ratio {dark_ratio:.2f}",
            debug=debug,
        )

    # 5b. Cinto AUSENTE: torso CLARO E ZERO diagonais.
    if dark_ratio < dark_min and diag_count == 0:
        return HeuristicaDecisao(
            cinto_visivel=False,
            confidence=0.65,
            score=score,
            contraste_suficiente=True,
            torso_visivel=True,
            evidence=f"torso claro · zero diagonais · sem indício de cinto (dark_ratio {dark_ratio:.2f})",
            debug=debug,
        )

    # 5c. Tudo o mais → INCONCLUSIVO (mantém pendente revisão humana)
    motivo = ""
    if dark_ratio > 0.65:
        motivo = "torso quase todo escuro (jaqueta fechada?)"
    elif diag_count == 0:
        motivo = "sem diagonal mas torso não claro"
    elif diag_count == 1:
        motivo = "apenas 1 diagonal — abaixo do threshold de confirmação"
    else:
        motivo = "ambíguo"
    return HeuristicaDecisao(
        cinto_visivel=None,
        confidence=0.0,
        score=score,
        contraste_suficiente=contraste_suficiente,
        torso_visivel=True,
        evidence=f"{motivo} (dark_ratio {dark_ratio:.2f}, diag={diag_count})",
        debug=debug,
    )


def _claude_decide(image_bgr: np.ndarray) -> dict | None:
    """
    Fallback VLM via Claude API (Haiku 4.5) quando heurística é inconclusiva.
    Retorna None se ANTHROPIC_API_KEY não estiver configurada.

    Pergunta atômica: "Há um cinto de segurança cruzando o torso do condutor?"
    """
    import base64
    import json
    import os

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import httpx
    except ImportError:
        return None

    ok, buf = cv2.imencode(".jpg", image_bgr, [cv2.IMWRITE_JPEG_QUALITY, 80])
    if not ok:
        return None
    b64 = base64.b64encode(buf.tobytes()).decode()

    prompt = (
        "Analise apenas o CONDUTOR (lado direito da imagem) na câmera interna "
        "de um exame de direção. Há cinto de segurança cruzando o peito dele "
        "(faixa diagonal indo do ombro esquerdo até a cintura direita)? "
        'Responda APENAS em JSON: {"cinto_visivel": true|false|null, '
        '"confidence": 0.0..1.0, "evidence": "<=15 palavras"}.'
    )

    payload = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 200,
        "temperature": 0.0,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    }
    try:
        r = httpx.post(
            "https://api.anthropic.com/v1/messages",
            json=payload,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            timeout=30.0,
        )
        r.raise_for_status()
        data = r.json()
        text = "\n".join(b["text"] for b in data["content"] if b["type"] == "text")
        clean = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        out = json.loads(clean)
        return {
            "cinto_visivel": out.get("cinto_visivel"),
            "confidence": float(out.get("confidence") or 0.0),
            "evidence": (out.get("evidence") or "")[:120],
            "_source": "claude-haiku-4-5",
        }
    except Exception as e:
        return {"_error": str(e), "_source": "claude-haiku-4-5"}


def heuristica_callback_factory(pose_path: Path | None, allow_vlm: bool = True):
    """
    Callback compatível com cinto_sampler.amostrar_cinto(vlm_callback=...).
    Pipeline em camadas:
      1. Heurística determinística HSV+Hough
      2. Se inconclusivo E allow_vlm E ANTHROPIC_API_KEY existe → Claude Haiku
      3. Caso contrário, mantém inconclusivo
    """
    if pose_path and pose_path.exists():
        import json

        with contextlib.suppress(Exception):
            json.loads(pose_path.read_text())

    def callback(image_bgr: np.ndarray, prompt: str) -> dict:
        decisao = avaliar_frame(image_bgr, pose_persons=None)
        result = {
            "torso_visivel": decisao.torso_visivel,
            "contraste_suficiente": decisao.contraste_suficiente,
            "cinto_visivel": decisao.cinto_visivel,
            "confidence": decisao.confidence,
            "evidence": decisao.evidence,
            "_score": decisao.score,
            "_debug": decisao.debug,
            "_layer": "heuristica",
        }
        # Se heurística não decide e VLM disponível, escala
        if decisao.cinto_visivel is None and allow_vlm:
            vlm = _claude_decide(image_bgr)
            if vlm and vlm.get("cinto_visivel") is not None:
                result["cinto_visivel"] = vlm["cinto_visivel"]
                result["confidence"] = vlm["confidence"]
                result["evidence"] = vlm["evidence"]
                result["_layer"] = "vlm:claude-haiku-4-5"
        return result

    return callback
