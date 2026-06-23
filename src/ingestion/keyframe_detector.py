"""
Keyframe Detector — filtra frames que merecem análise do VLM.

Usa heurísticas baratas em CPU:
  - Mudança de cena (diff de histograma)
  - Movimento brusco (optical flow magnitude)
  - Anomalia de iluminação
  - Amostragem regular obrigatória

Limitação conhecida: em cenas de pouco movimento (pátio de manobras),
pode perder eventos. Solução nos detectores específicos (road_text, etc.)
"""

from dataclasses import dataclass
from enum import StrEnum

import cv2
import numpy as np


class KeyframeReason(StrEnum):
    SCENE_CHANGE = "scene_change"
    HIGH_MOTION = "high_motion"
    AUDIO_PEAK = "audio_peak"
    LIGHTING_ANOMALY = "lighting_anomaly"
    SCHEDULED = "scheduled"


@dataclass
class Keyframe:
    timestamp_s: float
    frame_idx: int
    score: float
    reasons: list[KeyframeReason]
    camera_hint: str | None = None


class KeyframeDetector:
    def __init__(
        self,
        scene_threshold: float = 0.35,
        motion_threshold: float = 2.5,
        min_interval_s: float = 2.0,
        scheduled_every_s: float = 3.0,  # baixado de 10s após feedback real
    ):
        self.scene_threshold = scene_threshold
        self.motion_threshold = motion_threshold
        self.min_interval_s = min_interval_s
        self.scheduled_every_s = scheduled_every_s

    @staticmethod
    def _histogram(gray: np.ndarray) -> np.ndarray:
        hist = cv2.calcHist([gray], [0], None, [64], [0, 256])
        cv2.normalize(hist, hist)
        return hist

    @staticmethod
    def _optical_flow_magnitude(prev_gray: np.ndarray, curr_gray: np.ndarray) -> float:
        flow = cv2.calcOpticalFlowFarneback(
            prev_gray,
            curr_gray,
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

    def detect(self, grid_frames: list) -> list[Keyframe]:
        if len(grid_frames) < 2:
            return []

        keyframes: list[Keyframe] = []
        last_kept_ts = -float("inf")
        last_scheduled_ts = -float("inf")
        prev_gray_by_cam: dict[str, np.ndarray] = {}
        prev_hist_by_cam: dict[str, np.ndarray] = {}

        for gf in grid_frames:
            cameras = {
                "frontal": gf.frontal,
                "lateral_direita": gf.lateral_direita,
                "interna": gf.interna,
                "traseira_esq": gf.traseira_esq,
            }
            frame_reasons: list[KeyframeReason] = []
            frame_score = 0.0
            strongest_camera: str | None = None

            for cam_name, img in cameras.items():
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                hist = self._histogram(gray)

                if cam_name in prev_gray_by_cam:
                    corr = cv2.compareHist(prev_hist_by_cam[cam_name], hist, cv2.HISTCMP_CORREL)
                    if corr < self.scene_threshold:
                        frame_reasons.append(KeyframeReason.SCENE_CHANGE)
                        s = 1.0 - corr
                        if s > frame_score:
                            frame_score = s
                            strongest_camera = cam_name

                    small_prev = cv2.resize(prev_gray_by_cam[cam_name], (160, 90))
                    small_curr = cv2.resize(gray, (160, 90))
                    mag = self._optical_flow_magnitude(small_prev, small_curr)
                    if mag > self.motion_threshold:
                        frame_reasons.append(KeyframeReason.HIGH_MOTION)
                        s = min(1.0, mag / 10.0)
                        if s > frame_score:
                            frame_score = s
                            strongest_camera = cam_name

                    mean_lum = gray.mean()
                    prev_lum = prev_gray_by_cam[cam_name].mean()
                    if abs(mean_lum - prev_lum) > 60:
                        frame_reasons.append(KeyframeReason.LIGHTING_ANOMALY)

                prev_gray_by_cam[cam_name] = gray
                prev_hist_by_cam[cam_name] = hist

            if gf.timestamp_s - last_scheduled_ts >= self.scheduled_every_s:
                if not frame_reasons:
                    frame_reasons.append(KeyframeReason.SCHEDULED)
                    frame_score = max(frame_score, 0.2)
                last_scheduled_ts = gf.timestamp_s

            if frame_reasons and (gf.timestamp_s - last_kept_ts) >= self.min_interval_s:
                keyframes.append(
                    Keyframe(
                        timestamp_s=gf.timestamp_s,
                        frame_idx=gf.frame_idx,
                        score=round(frame_score, 3),
                        reasons=list(set(frame_reasons)),
                        camera_hint=strongest_camera,
                    )
                )
                last_kept_ts = gf.timestamp_s

        return keyframes
