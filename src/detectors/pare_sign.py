"""
Detector dedicado da placa R-1 (PARE) brasileira — câmera FRONTAL.

Por que existe:
  YOLO base COCO foi treinado em "stop sign" americana e generaliza mal pra
  placa R-1 brasileira (mesma forma octogonal mas tipografia/proporções
  diferentes). Em bbox pequeno (placa distante, 30-50 px) o YOLO confunde
  com qualquer silhueta cinza.

Heurística determinística:
  1. Máscara HSV de vermelho saturado (cobre os 2 ranges H≈0 e H≈180)
  2. Morphological close pra fechar a forma
  3. Contornos com área 200-12000 px², aspect ratio próximo de 1
  4. Aproximação de polígono — aceita 6-12 vértices (octógono pode aparecer
     com 6 a 12 lados após perspectiva e ruído)
  5. Fill ratio: pixels vermelhos dentro do bbox ≥ 60%

Saída: DetectionCandidate com confidence 0.4-0.95.

Custo: ~5ms por frame @ 640×360 em CPU.

Limitações:
  - Para-choques traseiros vermelhos brilhantes podem disparar (mas filtro
    de aspect e octogonalidade reduz)
  - Outras placas vermelhas (R-2 dê preferência, R-3 sentido proibido) também
    podem disparar — todas ainda são sinalização vertical relevante para
    R1020-G-a, então é aceitável como segunda fonte para revisão.
"""

from __future__ import annotations

import cv2
import numpy as np

from src.detectors.base import BaseDetector, DetectionCandidate, EventType


class PareSignDetector(BaseDetector):
    """Detecta placa octogonal vermelha (R-1 PARE)."""

    event_type = EventType.PARE_SIGN

    def __init__(
        self,
        min_area: int = 200,
        max_area: int = 12000,
        min_aspect: float = 0.7,
        max_aspect: float = 1.4,
        min_vertices: int = 6,
        max_vertices: int = 12,
        min_fill_ratio: float = 0.55,
        min_white_center: float = 0.04,
        max_white_center: float = 0.45,
        camera: str = "TL",
    ):
        self.min_area = min_area
        self.max_area = max_area
        self.min_aspect = min_aspect
        self.max_aspect = max_aspect
        self.min_vertices = min_vertices
        self.max_vertices = max_vertices
        self.min_fill_ratio = min_fill_ratio
        # Centro da placa R-1 tem "PARE" branco — fração de branco saturado
        # no ROI deve estar nessa janela. Outdoor/muro/carro: ou tem branco
        # demais (logo grande) ou nenhum. Placa: 4-45% branco aproximadamente.
        self.min_white_center = min_white_center
        self.max_white_center = max_white_center
        self.camera = camera

    @staticmethod
    def _red_mask(bgr: np.ndarray) -> np.ndarray:
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        # vermelho saturado em 2 ranges
        m1 = cv2.inRange(hsv, (0, 110, 70), (10, 255, 255))
        m2 = cv2.inRange(hsv, (170, 110, 70), (180, 255, 255))
        mask = cv2.bitwise_or(m1, m2)
        # fecha furos (texto branco "PARE" no centro vira buraco na máscara)
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        # remove sujeira pequena
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), iterations=1)
        return mask

    def detect(
        self,
        frame: np.ndarray,
        frame_idx: int = 0,
        timestamp_s: float = 0.0,
    ) -> DetectionCandidate:
        mask = self._red_mask(frame)
        # Máscara de branco saturado para checar texto "PARE" no centro da placa
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        white_mask = cv2.inRange(hsv, (0, 0, 180), (180, 50, 255))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        best: dict | None = None
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if not (self.min_area <= area <= self.max_area):
                continue
            x, y, w, h = cv2.boundingRect(cnt)
            if h == 0:
                continue
            aspect = w / h
            if not (self.min_aspect <= aspect <= self.max_aspect):
                continue

            # poligonalidade
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.025 * peri, True)
            n_vert = len(approx)
            if not (self.min_vertices <= n_vert <= self.max_vertices):
                continue

            # fill ratio: quanto do bbox é vermelho de fato
            roi_mask = mask[y : y + h, x : x + w]
            if roi_mask.size == 0:
                continue
            fill = float(cv2.countNonZero(roi_mask)) / roi_mask.size
            if fill < self.min_fill_ratio:
                continue

            # branco saturado no centro (texto "PARE") — discrimina muro/carro
            roi_white = white_mask[y : y + h, x : x + w]
            white_center = (
                float(cv2.countNonZero(roi_white)) / roi_white.size if roi_white.size > 0 else 0.0
            )
            if not (self.min_white_center <= white_center <= self.max_white_center):
                continue

            # score combinado
            aspect_score = 1.0 - abs(aspect - 1.0)  # melhor em 1.0
            vert_score = 1.0 - abs(n_vert - 8) / 6  # melhor em 8
            area_score = min(1.0, area / 4000.0)  # placas próximas valem mais
            # branco_score: pico em ~0.18 (palavra PARE ocupa ~15-25% do interior)
            white_score = 1.0 - min(1.0, abs(white_center - 0.18) / 0.18)
            score = (
                0.30 * fill
                + 0.20 * aspect_score
                + 0.15 * vert_score
                + 0.15 * area_score
                + 0.20 * white_score
            )
            if best is None or score > best["score"]:
                best = {
                    "score": score,
                    "bbox": (x, y, x + w, y + h),
                    "area": int(area),
                    "aspect": round(aspect, 2),
                    "n_vertices": n_vert,
                    "fill_ratio": round(fill, 3),
                    "white_center": round(white_center, 3),
                }

        if best is None:
            return DetectionCandidate(
                event_type=self.event_type,
                detected=False,
                confidence=0.0,
                bbox=None,
                camera=self.camera,
                frame_idx=frame_idx,
                timestamp_s=timestamp_s,
                metadata={},
            )

        confidence = float(min(0.95, max(0.4, best["score"])))
        return DetectionCandidate(
            event_type=self.event_type,
            detected=True,
            confidence=confidence,
            bbox=best["bbox"],
            camera=self.camera,
            frame_idx=frame_idx,
            timestamp_s=timestamp_s,
            metadata={
                "area": best["area"],
                "aspect": best["aspect"],
                "n_vertices": best["n_vertices"],
                "fill_ratio": best["fill_ratio"],
                "white_center": best["white_center"],
                "evidence": "R-1?",  # OCR pode confirmar PARE depois
                "score": round(best["score"], 3),
            },
        )
