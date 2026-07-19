from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .config import DetectorConfig, ZoneConfig


@dataclass(frozen=True)
class ZoneReading:
    id: str
    label: str
    occupancy: float
    occupied: bool


@dataclass(frozen=True)
class DetectionSnapshot:
    calibrated: bool
    calibrated_now: bool
    candidate_id: str | None
    candidate_confidence: float
    ambiguous: bool
    zones: tuple[ZoneReading, ...]
    mask: np.ndarray | None


@dataclass
class _ZoneGate:
    occupied: bool = False
    high_frames: int = 0
    low_frames: int = 0


class BackgroundZoneDetector:
    """Lightweight foreground detector for camera-defined surface zones."""

    def __init__(
        self,
        config: DetectorConfig,
        zones: tuple[ZoneConfig, ...],
        processing_resolution: tuple[int, int],
    ):
        self.config = config
        self.zones = zones
        self.processing_resolution = processing_resolution
        self._background: np.ndarray | None = None
        self._calibration_requested = True
        self._gates = {zone.id: _ZoneGate() for zone in zones}

    @property
    def calibrated(self) -> bool:
        return self._background is not None

    def request_calibration(self) -> None:
        self._calibration_requested = True

    def _prepare(self, frame: np.ndarray) -> np.ndarray:
        width, height = self.processing_resolution
        resized = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        return cv2.GaussianBlur(gray, (7, 7), 0)

    def _zone_bounds(self, zone: ZoneConfig) -> tuple[int, int, int, int]:
        width, height = self.processing_resolution
        x0, y0, x1, y1 = zone.rect
        return (
            max(0, min(width - 1, round(x0 * width))),
            max(0, min(height - 1, round(y0 * height))),
            max(1, min(width, round(x1 * width))),
            max(1, min(height, round(y1 * height))),
        )

    def _reset_gates(self) -> None:
        for gate in self._gates.values():
            gate.occupied = False
            gate.high_frames = 0
            gate.low_frames = 0

    def analyze(self, frame: np.ndarray) -> DetectionSnapshot:
        prepared = self._prepare(frame)
        if self._background is None or self._calibration_requested:
            self._background = prepared.astype(np.float32)
            self._calibration_requested = False
            self._reset_gates()
            return DetectionSnapshot(
                calibrated=True,
                calibrated_now=True,
                candidate_id=None,
                candidate_confidence=0.0,
                ambiguous=False,
                zones=tuple(ZoneReading(zone.id, zone.label, 0.0, False) for zone in self.zones),
                mask=np.zeros_like(prepared),
            )

        background_u8 = cv2.convertScaleAbs(self._background)
        difference = cv2.absdiff(prepared, background_u8)
        _, mask = cv2.threshold(difference, self.config.pixel_threshold, 255, cv2.THRESH_BINARY)
        kernel = np.ones((5, 5), dtype=np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)

        readings: list[ZoneReading] = []
        for zone in self.zones:
            x0, y0, x1, y1 = self._zone_bounds(zone)
            roi = mask[y0:y1, x0:x1]
            occupancy = float(cv2.countNonZero(roi)) / float(max(1, roi.size))
            gate = self._gates[zone.id]

            if occupancy >= self.config.press_ratio:
                gate.high_frames += 1
                gate.low_frames = 0
                if gate.high_frames >= self.config.press_frames:
                    gate.occupied = True
            elif occupancy <= self.config.release_ratio:
                gate.low_frames += 1
                gate.high_frames = 0
                if gate.low_frames >= self.config.release_frames:
                    gate.occupied = False
            else:
                gate.high_frames = 0
                gate.low_frames = 0

            readings.append(ZoneReading(zone.id, zone.label, occupancy, gate.occupied))

        occupied = [reading for reading in readings if reading.occupied]
        ambiguous = len(occupied) > 1
        candidate = occupied[0] if len(occupied) == 1 else None
        confidence = 0.0
        if candidate is not None:
            confidence = min(1.0, candidate.occupancy / max(self.config.press_ratio * 2.0, 0.01))

        # Adapt very slowly only when no control is occupied. This handles
        # gradual daylight drift while avoiding learning a hand into the background.
        if not occupied and self.config.adapt_rate > 0:
            cv2.accumulateWeighted(prepared, self._background, self.config.adapt_rate)

        return DetectionSnapshot(
            calibrated=True,
            calibrated_now=False,
            candidate_id=candidate.id if candidate else None,
            candidate_confidence=confidence,
            ambiguous=ambiguous,
            zones=tuple(readings),
            mask=mask,
        )
