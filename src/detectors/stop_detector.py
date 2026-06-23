"""
Detector de parada do veículo — reutilizado pelos prompts PARE, LRE, zebra.

Heurística:
  Optical flow denso (Farneback) entre 2 frames consecutivos.
  Se magnitude média do flow < threshold → veículo parado.

  Importante: só analisa região inferior do frame (pista) para não confundir
  com movimento de carros passando, árvores balançando, etc.

Uso típico:
  detector = StopDetector()
  is_stopped = detector.is_stopped_in_window(
      frames=[frame_at_T-2, frame_at_T-1, frame_at_T, frame_at_T+1, frame_at_T+2]
  )
  # retorna True se em algum sub-intervalo o carro ficou imóvel por >=1s

Custo: ~30ms para flow entre 2 frames @ 640×360 downscaled para 160×90.
"""

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class StopEvent:
    started_at_s: float
    duration_s: float
    confidence: float


class StopDetector:
    def __init__(
        self,
        motion_threshold: float = 0.8,  # magnitude média do flow
        min_stop_duration_s: float = 0.8,  # parada real requer esta duração
        downscale_to: tuple[int, int] = (160, 90),
    ):
        self.motion_threshold = motion_threshold
        self.min_stop_duration_s = min_stop_duration_s
        self.downscale_to = downscale_to

    def _flow_magnitude(self, prev_bgr: np.ndarray, curr_bgr: np.ndarray) -> float:
        """Optical flow médio na metade inferior (foco na pista)."""
        prev = cv2.cvtColor(prev_bgr, cv2.COLOR_BGR2GRAY)
        curr = cv2.cvtColor(curr_bgr, cv2.COLOR_BGR2GRAY)
        # usa só metade inferior para não pegar movimento de céu/árvores
        h = prev.shape[0]
        prev = cv2.resize(prev[h // 2 :, :], self.downscale_to)
        curr = cv2.resize(curr[h // 2 :, :], self.downscale_to)

        flow = cv2.calcOpticalFlowFarneback(
            prev,
            curr,
            None,
            pyr_scale=0.5,
            levels=2,
            winsize=15,
            iterations=2,
            poly_n=5,
            poly_sigma=1.1,
            flags=0,
        )
        mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
        return float(mag.mean())

    def is_stopped_in_window(
        self, frames: list[np.ndarray], timestamps_s: list[float]
    ) -> StopEvent | None:
        """
        Recebe frames consecutivos e seus timestamps.
        Retorna StopEvent se em algum sub-intervalo o carro ficou parado
        por >= min_stop_duration_s; None caso contrário.
        """
        if len(frames) < 2:
            return None

        magnitudes = []
        for i in range(len(frames) - 1):
            mag = self._flow_magnitude(frames[i], frames[i + 1])
            magnitudes.append(mag)

        # acha trechos contíguos onde magnitude < threshold
        stopped_start_idx = None
        best_event: StopEvent | None = None
        for i, mag in enumerate(magnitudes):
            if mag < self.motion_threshold:
                if stopped_start_idx is None:
                    stopped_start_idx = i
            else:
                if stopped_start_idx is not None:
                    duration = timestamps_s[i] - timestamps_s[stopped_start_idx]
                    if duration >= self.min_stop_duration_s:
                        event = StopEvent(
                            started_at_s=timestamps_s[stopped_start_idx],
                            duration_s=duration,
                            confidence=0.85,
                        )
                        if best_event is None or event.duration_s > best_event.duration_s:
                            best_event = event
                    stopped_start_idx = None

        # caso a janela inteira tenha sido parada
        if stopped_start_idx is not None:
            duration = timestamps_s[-1] - timestamps_s[stopped_start_idx]
            if duration >= self.min_stop_duration_s:
                event = StopEvent(
                    started_at_s=timestamps_s[stopped_start_idx],
                    duration_s=duration,
                    confidence=0.9,
                )
                if best_event is None or event.duration_s > best_event.duration_s:
                    best_event = event

        return best_event
