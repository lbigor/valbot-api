"""Detector de semáforo próximo — câmera FRONTAL."""

from typing import ClassVar

import cv2
import numpy as np

from src.detectors.base import BaseDetector, DetectionCandidate, EventType


class TrafficLightDetector(BaseDetector):
    event_type = EventType.TRAFFIC_LIGHT

    HSV_RANGES: ClassVar[dict[str, tuple[np.ndarray, np.ndarray]]] = {
        "red1": (np.array([0, 120, 140]), np.array([10, 255, 255])),
        "red2": (np.array([170, 120, 140]), np.array([180, 255, 255])),
        "yellow": (np.array([18, 130, 180]), np.array([32, 255, 255])),
        "green": (np.array([45, 100, 140]), np.array([85, 255, 255])),
    }

    def __init__(self, min_radius=3, max_radius=15, upper_roi_fraction=0.6):
        self.min_radius = min_radius
        self.max_radius = max_radius
        self.upper_roi_fraction = upper_roi_fraction

    def _color_mask(self, hsv):
        masks = {n: cv2.inRange(hsv, lo, hi) for n, (lo, hi) in self.HSV_RANGES.items()}
        masks["red"] = cv2.bitwise_or(masks.pop("red1"), masks.pop("red2"))
        return masks

    def _find_light_blobs(self, mask):
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        blobs = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < 9 or area > 700:
                continue
            (cx, cy), r = cv2.minEnclosingCircle(cnt)
            if not (self.min_radius <= r <= self.max_radius):
                continue
            if np.pi * r * r == 0:
                continue
            if area / (np.pi * r * r) < 0.55:
                continue
            blobs.append((int(cx), int(cy), int(r)))
        return blobs

    def detect(self, frame, frame_idx=0, timestamp_s=0.0):
        h, w = frame.shape[:2]
        roi_h = int(h * self.upper_roi_fraction)
        roi = frame[:roi_h, :]
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        masks = self._color_mask(hsv)
        all_blobs = []
        for color, mask in masks.items():
            for cx, cy, r in self._find_light_blobs(mask):
                all_blobs.append((cx, cy, r, color))

        if not all_blobs:
            return DetectionCandidate(
                event_type=self.event_type,
                detected=False,
                confidence=0.0,
                bbox=None,
                camera="TL",
                frame_idx=frame_idx,
                timestamp_s=timestamp_s,
                metadata={"blobs": 0},
            )

        confidence = 0.4
        colors = [b[3] for b in all_blobs]
        if "red" in colors:
            confidence += 0.3
        sorted_blobs = sorted(all_blobs, key=lambda b: b[0])
        aligned = 1
        for i in range(len(sorted_blobs) - 1):
            if abs(sorted_blobs[i][0] - sorted_blobs[i + 1][0]) < 15:
                aligned += 1
        if aligned >= 2:
            confidence += 0.2
        max_r = max(b[2] for b in all_blobs)
        if max_r >= 6:
            confidence += 0.1
        confidence = min(confidence, 0.95)

        xs = [b[0] - b[2] for b in all_blobs] + [b[0] + b[2] for b in all_blobs]
        ys = [b[1] - b[2] for b in all_blobs] + [b[1] + b[2] for b in all_blobs]
        x0, y0 = max(0, min(xs)), max(0, min(ys))
        x1, y1 = min(w, max(xs)), min(roi_h, max(ys))

        return DetectionCandidate(
            event_type=self.event_type,
            detected=True,
            confidence=confidence,
            bbox=(x0, y0, x1 - x0, y1 - y0),
            camera="TL",
            frame_idx=frame_idx,
            timestamp_s=timestamp_s,
            metadata={
                "blobs": len(all_blobs),
                "colors": colors,
                "max_radius": max_r,
                "aligned_vertically": aligned >= 2,
            },
        )
