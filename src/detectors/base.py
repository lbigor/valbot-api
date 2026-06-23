"""Base para detectores OpenCV."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum

import numpy as np


class EventType(StrEnum):
    PARE_SIGN = "pare_sign"
    CROSSWALK = "crosswalk"
    TRAFFIC_LIGHT = "traffic_light"
    STOP_LINE = "stop_line"
    CURB = "curb"
    VEHICLE_STOPPED = "vehicle_stopped"


@dataclass
class DetectionCandidate:
    event_type: EventType
    detected: bool
    confidence: float
    bbox: tuple[int, int, int, int] | None
    camera: str
    frame_idx: int
    timestamp_s: float
    metadata: dict

    @property
    def should_trigger_vlm(self) -> bool:
        return self.detected and self.confidence >= 0.45


class BaseDetector(ABC):
    event_type: EventType

    @abstractmethod
    def detect(
        self, frame: np.ndarray, frame_idx: int = 0, timestamp_s: float = 0.0
    ) -> DetectionCandidate: ...

    @staticmethod
    def _lower_roi(frame: np.ndarray, fraction: float = 0.5) -> np.ndarray:
        h = frame.shape[0]
        return frame[int(h * fraction) :, :]
