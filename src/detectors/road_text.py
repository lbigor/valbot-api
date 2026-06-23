"""
Detector de sinalização "PARE" pintada no asfalto — câmera FRONTAL (TL).

Heurística:
  1. ROI = metade inferior do frame (onde está o asfalto próximo)
  2. Threshold adaptativo para isolar branco do asfalto
  3. Contornos com área > 300px² e aspect ratio 1.5-4 (letras largas)
  4. Agrupamento: 3-4 contornos próximos na mesma altura = texto (P-A-R-E)
  5. Confirmação: pixels brancos acima de 6% da ROI indica marcação significativa

Custo: ~20ms por frame @ 640×360 em CPU.

Limitação conhecida: não distingue "PARE" de "DE DIREI[ÇÃO]" ou outros textos
horizontais. Ambos ainda são sinalização relevante que merece abrir janela
temporal — o VLM decide depois qual texto é exatamente.

Por isso o detector é chamado "road_text" e não "pare" — ele dispara para
QUALQUER texto grande no asfalto próximo.
"""

import logging

import cv2
import numpy as np

from src.detectors.base import BaseDetector, DetectionCandidate, EventType

log = logging.getLogger(__name__)

_OCR_READER: object | None = None
_OCR_DISABLED = False


def _get_ocr():
    """Singleton easyocr Reader. Lazy import — falha silenciosa se ausente."""
    global _OCR_READER, _OCR_DISABLED
    if _OCR_DISABLED:
        return None
    if _OCR_READER is not None:
        return _OCR_READER
    try:
        import easyocr

        _OCR_READER = easyocr.Reader(["pt"], gpu=False, verbose=False)
        return _OCR_READER
    except Exception as e:
        print(f"[road_text] OCR indisponível ({e}); seguindo sem OCR")
        _OCR_DISABLED = True
        return None


_PARE_TOKENS = {"pare", "parc", "parf", "pare.", "pare!"}


def _classify_text(raw: str) -> str:
    """
    Devolve 'PARE' se o OCR achou algo que parece "PARE" no asfalto,
    'CROSSWALK' para faixas/zebra, ou retorna o texto cru caso contrário.
    """
    t = (raw or "").strip().lower()
    if not t:
        return ""
    if t in _PARE_TOKENS or "pare" in t.split():
        return "PARE"
    if "lombada" in t:
        return "LOMBADA"
    if "devagar" in t:
        return "DEVAGAR"
    if "escola" in t:
        return "ESCOLA"
    return raw.strip().upper()[:32]


class RoadTextDetector(BaseDetector):
    """Detecta texto ou sinalização branca grande pintada no asfalto."""

    event_type = EventType.PARE_SIGN  # event_type abrange todo texto no chão

    def __init__(
        self,
        min_contour_area: int = 300,
        max_contour_area: int = 4500,
        min_letter_aspect: float = 0.4,
        max_letter_aspect: float = 3.5,
        min_cluster_size: int = 2,
        white_threshold: int = 180,
    ):
        self.min_contour_area = min_contour_area
        self.max_contour_area = max_contour_area
        self.min_letter_aspect = min_letter_aspect
        self.max_letter_aspect = max_letter_aspect
        self.min_cluster_size = min_cluster_size
        self.white_threshold = white_threshold

    def _isolate_white_on_asphalt(self, bgr_roi: np.ndarray) -> np.ndarray:
        """Isola pixels brancos brilhantes. Assume asfalto cinza/escuro."""
        gray = cv2.cvtColor(bgr_roi, cv2.COLOR_BGR2GRAY)
        # threshold de branco (pavimento fica < 180, tinta fica > 200)
        _, mask = cv2.threshold(gray, self.white_threshold, 255, cv2.THRESH_BINARY)
        # limpa sujeira pequena
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)
        return mask

    def _letter_candidates(self, mask: np.ndarray) -> list[tuple[int, int, int, int]]:
        """Extrai contornos com formato de letra. Retorna bounding boxes (x,y,w,h)."""
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        letters = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if not (self.min_contour_area <= area <= self.max_contour_area):
                continue
            x, y, w, h = cv2.boundingRect(cnt)
            if h == 0:
                continue
            aspect = w / h  # largura/altura
            if not (self.min_letter_aspect <= aspect <= self.max_letter_aspect):
                continue
            letters.append((x, y, w, h))
        return letters

    def _cluster_letters(
        self, letters: list[tuple[int, int, int, int]], y_tolerance: int = 25
    ) -> list[list]:
        """Agrupa letras que estão aproximadamente na mesma linha horizontal."""
        if not letters:
            return []
        letters = sorted(letters, key=lambda b: b[1])  # por Y

        clusters = []
        current = [letters[0]]
        for letter in letters[1:]:
            # Compara centro Y com média do cluster atual
            mean_y = np.mean([item[1] + item[3] / 2 for item in current])
            this_y = letter[1] + letter[3] / 2
            if abs(this_y - mean_y) < y_tolerance:
                current.append(letter)
            else:
                clusters.append(current)
                current = [letter]
        clusters.append(current)
        return clusters

    def detect(
        self, frame: np.ndarray, frame_idx: int = 0, timestamp_s: float = 0.0
    ) -> DetectionCandidate:
        h, w = frame.shape[:2]
        roi = self._lower_roi(frame, fraction=0.50)  # metade inferior
        mask = self._isolate_white_on_asphalt(roi)

        # fração de pixels brancos na ROI (filtro rápido)
        white_ratio = float(np.count_nonzero(mask)) / mask.size
        if white_ratio < 0.015:  # pouca marcação no asfalto
            return DetectionCandidate(
                event_type=self.event_type,
                detected=False,
                confidence=0.0,
                bbox=None,
                camera="TL",
                frame_idx=frame_idx,
                timestamp_s=timestamp_s,
                metadata={"white_ratio": round(white_ratio, 4)},
            )

        letters = self._letter_candidates(mask)
        clusters = self._cluster_letters(letters)

        best_cluster = max(clusters, key=len) if clusters else []

        detected = len(best_cluster) >= self.min_cluster_size

        if not detected:
            return DetectionCandidate(
                event_type=self.event_type,
                detected=False,
                confidence=0.15,
                bbox=None,
                camera="TL",
                frame_idx=frame_idx,
                timestamp_s=timestamp_s,
                metadata={
                    "white_ratio": round(white_ratio, 4),
                    "contours_found": len(letters),
                    "best_cluster_size": len(best_cluster),
                },
            )

        # Confidence heuristics
        confidence = 0.45
        if len(best_cluster) >= 3:
            confidence += 0.2  # PARE tem 4 letras
        if len(best_cluster) >= 4:
            confidence += 0.1
        if white_ratio > 0.04:
            confidence += 0.1  # muito branco = sinalização grande
        # proximidade: letras maiores = mais perto
        max_letter_h = max(item[3] for item in best_cluster)
        if max_letter_h >= 35:
            confidence += 0.15

        confidence = min(confidence, 0.95)

        # bbox envolvente das letras (em coord absoluta, somando offset da ROI)
        roi_y_offset = h // 2
        xs = [item[0] for item in best_cluster] + [item[0] + item[2] for item in best_cluster]
        ys = [item[1] + roi_y_offset for item in best_cluster] + [
            item[1] + item[3] + roi_y_offset for item in best_cluster
        ]
        x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)

        # OCR no recorte ampliado (10px de padding) — só roda se cluster passou
        evidence = ""
        ocr_raw = ""
        ocr = _get_ocr()
        if ocr is not None:
            pad = 10
            cx0, cy0 = max(0, x0 - pad), max(0, y0 - pad)
            cx1, cy1 = min(w, x1 + pad), min(h, y1 + pad)
            crop = frame[cy0:cy1, cx0:cx1]
            if crop.size > 0:
                try:
                    # contrast=0.5 ajuda em texto descolorido no asfalto
                    raw_results = ocr.readtext(
                        crop,
                        detail=1,
                        paragraph=False,
                        contrast_ths=0.05,
                        adjust_contrast=0.7,
                    )
                    if raw_results:
                        # pega palavra com maior confiança
                        best = max(raw_results, key=lambda r: r[2])
                        ocr_raw = str(best[1] or "")
                        float(best[2] or 0.0)
                        evidence = _classify_text(ocr_raw)
                        if evidence == "PARE":
                            confidence = min(0.95, confidence + 0.25)
                        elif evidence and evidence not in ("CROSSWALK",):
                            # OCR pegou algo coerente → bump menor
                            confidence = min(0.9, confidence + 0.05)
                except Exception as e:
                    # OCR falhou nesse frame — segue sem evidência
                    log.debug("OCR PARE/ESCOLA falhou frame_idx=%s: %s", frame_idx, e)

        return DetectionCandidate(
            event_type=self.event_type,
            detected=True,
            confidence=confidence,
            bbox=(x0, y0, x1 - x0, y1 - y0),
            camera="TL",
            frame_idx=frame_idx,
            timestamp_s=timestamp_s,
            metadata={
                "white_ratio": round(white_ratio, 4),
                "letters_in_cluster": len(best_cluster),
                "max_letter_height": max_letter_h,
                "evidence": evidence,
                "ocr_raw": ocr_raw,
            },
        )
