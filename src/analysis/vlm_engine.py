"""
VLM Engine — análise visual dos keyframes.

Estratégia híbrida:
    1. Qwen2.5-VL local faz triagem em TODOS os keyframes (barato)
    2. Frames com suspeita alta vão pro Claude API (Sonnet) para validação
    3. Resultado final mescla ambos, priorizando Claude quando disponível

Determinismo: temperature=0, seed fixo, prompt idêntico sempre.
Cada inferência é hasheada e cacheada (SHA-256 do frame + prompt).
"""

import base64
import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DetectionResult:
    infracao_id: str
    camera: str
    timestamp_s: float
    frame_idx: int
    detected: bool
    confidence: float
    evidence: str
    model_name: str


@dataclass
class FrameAnalysis:
    timestamp_s: float
    frame_idx: int
    camera: str
    detections: list[DetectionResult]
    needs_review: bool = False
    raw_model_output: str = ""


class VLMBackend(ABC):
    model_name: str

    @abstractmethod
    def analyze(self, image_bgr, user_prompt: str, system_prompt: str) -> str: ...


class QwenVLBackend(VLMBackend):
    """
    Stub — implementação real depende do ambiente.
    No Mac: mlx-vlm com Qwen2.5-VL-3B-Instruct-4bit
    No Linux/CUDA: transformers com Qwen2.5-VL-7B-Instruct
    """

    def __init__(self, model_size: str = "7B", device: str = "auto"):
        self.model_name = f"qwen2.5-vl-{model_size.lower()}"
        self.model_size = model_size
        self.device = device

    def analyze(self, image_bgr, user_prompt: str, system_prompt: str) -> str:
        raise NotImplementedError("Implementar conforme ambiente (MLX ou transformers)")


class ClaudeBackend(VLMBackend):
    """Usa Anthropic API (claude-sonnet-4) para frames de alto valor."""

    model_name = "claude-sonnet-4"

    def __init__(self, api_key: str | None = None):
        import os

        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY não configurada")

    def analyze(self, image_bgr, user_prompt: str, system_prompt: str) -> str:
        import cv2
        import httpx

        ok, buf = cv2.imencode(".jpg", image_bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ok:
            raise RuntimeError("Falha ao codificar frame em JPEG")
        b64 = base64.b64encode(buf.tobytes()).decode()

        payload = {
            "model": "claude-sonnet-4-5",
            "max_tokens": 1500,
            "temperature": 0.0,
            "system": system_prompt,
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
                        {"type": "text", "text": user_prompt},
                    ],
                }
            ],
        }
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        r = httpx.post(
            "https://api.anthropic.com/v1/messages", json=payload, headers=headers, timeout=60.0
        )
        r.raise_for_status()
        data = r.json()
        texts = [b["text"] for b in data["content"] if b["type"] == "text"]
        return "\n".join(texts)


class HybridVLMEngine:
    def __init__(
        self,
        local_backend: VLMBackend | None = None,
        cloud_backend: VLMBackend | None = None,
        cache_dir: Path = Path("./.vlm_cache"),
        escalation_threshold: float = 0.7,
    ):
        self.local = local_backend
        self.cloud = cloud_backend
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.escalation_threshold = escalation_threshold

        if not (local_backend or cloud_backend):
            raise ValueError("Pelo menos um backend precisa estar configurado")

    def _cache_key(self, image_bgr, prompt: str, model: str) -> Path:
        import cv2

        _ok, buf = cv2.imencode(".jpg", image_bgr, [cv2.IMWRITE_JPEG_QUALITY, 70])
        frame_hash = hashlib.sha256(buf.tobytes()).hexdigest()[:16]
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:8]
        return self.cache_dir / f"{model}_{frame_hash}_{prompt_hash}.json"

    def _parse(
        self, raw: str, camera: str, ts: float, frame_idx: int, model_name: str, infracao_id: str
    ) -> FrameAnalysis:
        try:
            clean = raw.strip().removeprefix("```json").removeprefix("```")
            clean = clean.removesuffix("```").strip()
            data = json.loads(clean)
            detections = [
                DetectionResult(
                    infracao_id=infracao_id,
                    camera=camera,
                    timestamp_s=ts,
                    frame_idx=frame_idx,
                    detected=bool(data.get("detected", False)),
                    confidence=float(data.get("confidence", 0.0)),
                    evidence=data.get("evidence", ""),
                    model_name=model_name,
                )
            ]
            return FrameAnalysis(
                ts, frame_idx, camera, detections, needs_review=False, raw_model_output=raw
            )
        except (json.JSONDecodeError, KeyError, TypeError):
            return FrameAnalysis(ts, frame_idx, camera, [], needs_review=True, raw_model_output=raw)
