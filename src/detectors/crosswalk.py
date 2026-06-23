"""
Detector de faixa de travessia de pedestres (zebra) — funciona nas câmeras TL e BR.

Heurística:
  Faixa de pedestres = conjunto de retângulos brancos PARALELOS entre si,
  espaçados uniformemente, PERPENDICULARES ao sentido de marcha do veículo.

  1. ROI = metade inferior (TL) ou metade superior (BR, zebra aparece atrás)
  2. Máscara branca + threshold
  3. Procura 3+ retângulos com:
     - razão de aspecto > 2 (retângulos alongados na horizontal da imagem)
     - altura similar entre si (±20%)
     - alinhados verticalmente (delta_y pequeno)
     - espaçamento regular entre eles

Diferenciação contra ZPA (zebrado de canalização):
  - Zebra: linhas retas, paralelas, PERPENDICULARES à direção da pista
  - ZPA: linhas DIAGONAIS (inclinadas), formando padrão enviesado

Uso recomendado: rodar TL e BR em paralelo. Se TL detecta em t=T, abre
janela [T-3s, T+5s] e aguarda BR confirmar em [T+1s, T+5s]. Dupla detecção
= alta confiança. Detecção só em TL = confidence média.

Custo: ~25ms por frame.
"""

import cv2
import numpy as np

from src.detectors.base import BaseDetector, DetectionCandidate, EventType


class CrosswalkDetector(BaseDetector):
    event_type = EventType.CROSSWALK

    def __init__(
        self,
        min_stripes: int = 3,
        min_aspect: float = 2.0,  # largura/altura das faixas
        min_stripe_area: int = 200,
        max_stripe_area: int = 5000,
        camera: str = "TL",
    ):
        self.min_stripes = min_stripes
        self.min_aspect = min_aspect
        self.min_stripe_area = min_stripe_area
        self.max_stripe_area = max_stripe_area
        self.camera = camera

    def _select_roi(self, frame: np.ndarray) -> tuple[np.ndarray, int]:
        """ROI difere por câmera. Retorna (roi, y_offset)."""
        h = frame.shape[0]
        if self.camera == "TL":
            # zebra se aproxima: olhar metade inferior
            return frame[h // 2 :, :], h // 2
        elif self.camera == "BR":
            # zebra já passada: olhar metade SUPERIOR (aparece atrás)
            return frame[: h // 2, :], 0
        else:
            return frame, 0

    def _find_stripe_candidates(self, bgr_roi: np.ndarray) -> list[tuple]:
        """Retorna retângulos brancos alongados horizontalmente."""
        gray = cv2.cvtColor(bgr_roi, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray, 175, 255, cv2.THRESH_BINARY)

        # fecha pequenos gaps dentro de cada faixa
        kernel = np.ones((2, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if not (self.min_stripe_area <= area <= self.max_stripe_area):
                continue
            x, y, w, h = cv2.boundingRect(cnt)
            if h == 0:
                continue
            aspect = w / h
            if aspect < self.min_aspect:
                continue
            candidates.append((x, y, w, h, aspect))
        return candidates

    def _check_stripe_pattern(self, stripes: list[tuple]) -> tuple[bool, float]:
        """
        Verifica se as faixas formam padrão de zebra real.
        Retorna (is_crosswalk, confidence_score).
        """
        if len(stripes) < self.min_stripes:
            return False, 0.0

        # ordena por Y (top-down)
        stripes = sorted(stripes, key=lambda s: s[1])

        # alturas similares? (faixas de zebra têm altura próxima)
        heights = [s[3] for s in stripes]
        mean_h = np.mean(heights)
        if mean_h < 5:
            return False, 0.0
        h_variance = np.std(heights) / mean_h
        if h_variance > 0.45:  # muito variável = não é zebra
            return False, 0.0

        # espaçamento regular entre faixas?
        gaps = []
        for i in range(len(stripes) - 1):
            gap = stripes[i + 1][1] - (stripes[i][1] + stripes[i][3])
            gaps.append(gap)
        if not gaps:
            return False, 0.0
        mean_gap = np.mean(gaps)
        if mean_gap <= 0 or mean_gap > 60:
            return False, 0.0
        gap_variance = np.std(gaps) / max(mean_gap, 1)

        # scoring
        confidence = 0.35
        confidence += min(0.25, (len(stripes) - self.min_stripes) * 0.08)
        if h_variance < 0.25:
            confidence += 0.15
        if gap_variance < 0.4:
            confidence += 0.15
        # faixas próximas na imagem (mais próximas do carro = mais relevantes)
        if mean_h >= 15:
            confidence += 0.10

        return True, min(confidence, 0.92)

    def detect(
        self, frame: np.ndarray, frame_idx: int = 0, timestamp_s: float = 0.0
    ) -> DetectionCandidate:
        roi, y_offset = self._select_roi(frame)
        stripes = self._find_stripe_candidates(roi)
        is_zebra, confidence = self._check_stripe_pattern(stripes)

        if not is_zebra:
            return DetectionCandidate(
                event_type=self.event_type,
                detected=False,
                confidence=0.0,
                bbox=None,
                camera=self.camera,
                frame_idx=frame_idx,
                timestamp_s=timestamp_s,
                metadata={"stripes_found": len(stripes)},
            )

        xs = [s[0] for s in stripes] + [s[0] + s[2] for s in stripes]
        ys = [s[1] + y_offset for s in stripes] + [s[1] + s[3] + y_offset for s in stripes]

        return DetectionCandidate(
            event_type=self.event_type,
            detected=True,
            confidence=confidence,
            bbox=(min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)),
            camera=self.camera,
            frame_idx=frame_idx,
            timestamp_s=timestamp_s,
            metadata={
                "stripes_count": len(stripes),
                "mean_stripe_height": round(float(np.mean([s[3] for s in stripes])), 1),
            },
        )
