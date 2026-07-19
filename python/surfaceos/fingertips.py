from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class Fingertip:
    """A detected fingertip in normalized processing-frame coordinates (0..1)."""

    x: float
    y: float


@dataclass(frozen=True)
class FingertipParams:
    min_area_frac: float = 0.010
    defect_depth_frac: float = 0.020
    finger_angle_deg: float = 90.0
    merge_radius_frac: float = 0.030
    max_points: int = 10


def _angle_deg(start: np.ndarray, far: np.ndarray, end: np.ndarray) -> float:
    """Angle (degrees) at the valley point ``far`` between two hull points."""
    a = start - far
    b = end - far
    denom = float(np.linalg.norm(a) * np.linalg.norm(b)) + 1e-6
    cosine = float(np.dot(a, b)) / denom
    return math.degrees(math.acos(max(-1.0, min(1.0, cosine))))


def _merge_points(points: list[tuple[float, float]], radius: float) -> list[tuple[float, float]]:
    """Greedy clustering so a single finger is not reported as several tips."""
    merged: list[tuple[float, float]] = []
    for point in points:
        for index, existing in enumerate(merged):
            if math.hypot(point[0] - existing[0], point[1] - existing[1]) <= radius:
                merged[index] = ((existing[0] + point[0]) / 2.0, (existing[1] + point[1]) / 2.0)
                break
        else:
            merged.append(point)
    return merged


class FingertipTracker:
    """Extract fingertip points from a cleaned foreground mask.

    The mask is expected to already isolate the hand/object via background
    subtraction. Fingertips are the convex extremities that flank the deep
    valleys between fingers, with a topmost-point fallback for a single
    extended finger. This is orientation tolerant and needs no neural model,
    so it fits the UNO Q's 2 GB Debian side alongside the existing OpenCV path.
    """

    def __init__(self, params: FingertipParams):
        self.params = params

    def detect(self, mask: np.ndarray) -> list[Fingertip]:
        height, width = mask.shape[:2]
        if height == 0 or width == 0:
            return []

        frame_area = float(width * height)
        diagonal = math.hypot(width, height)
        min_area = self.params.min_area_frac * frame_area
        min_depth = self.params.defect_depth_frac * diagonal
        merge_radius = self.params.merge_radius_frac * diagonal

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        raw_points: list[tuple[float, float]] = []

        for contour in contours:
            if cv2.contourArea(contour) < min_area:
                continue

            points = contour.reshape(-1, 2).astype(np.float32)
            topmost = points[int(np.argmin(points[:, 1]))]
            raw_points.append((float(topmost[0]), float(topmost[1])))

            hull_indices = cv2.convexHull(contour, returnPoints=False)
            if hull_indices is None or len(hull_indices) <= 3:
                continue

            # convexityDefects requires monotonically increasing hull indices.
            hull_indices = np.sort(hull_indices.flatten())[:, None]
            try:
                defects = cv2.convexityDefects(contour, hull_indices)
            except cv2.error:
                defects = None
            if defects is None:
                continue

            for start_idx, end_idx, far_idx, fixpt_depth in defects[:, 0]:
                depth = fixpt_depth / 256.0
                if depth < min_depth:
                    continue
                start = points[start_idx]
                end = points[end_idx]
                far = points[far_idx]
                if _angle_deg(start, far, end) > self.params.finger_angle_deg:
                    continue
                raw_points.append((float(start[0]), float(start[1])))
                raw_points.append((float(end[0]), float(end[1])))

        merged = _merge_points(raw_points, merge_radius)
        merged.sort(key=lambda point: point[1])
        merged = merged[: self.params.max_points]
        return [Fingertip(x=point[0] / width, y=point[1] / height) for point in merged]
