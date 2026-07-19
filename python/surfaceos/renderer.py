from __future__ import annotations

import cv2
import numpy as np

from .config import ZoneConfig
from .detector import DetectionSnapshot
from .fusion import Selection


def _bounds(rect: tuple[float, float, float, float], width: int, height: int) -> tuple[int, int, int, int]:
    x0, y0, x1, y1 = rect
    return round(x0 * width), round(y0 * height), round(x1 * width), round(y1 * height)


def render_overlay(
    frame: np.ndarray,
    zones: tuple[ZoneConfig, ...],
    snapshot: DetectionSnapshot,
    selection: Selection | None,
    activation_mode: str,
    jpeg_quality: int,
) -> bytes:
    canvas = frame.copy()
    height, width = canvas.shape[:2]
    readings = {reading.id: reading for reading in snapshot.zones}

    for zone in zones:
        x0, y0, x1, y1 = _bounds(zone.rect, width, height)
        reading = readings[zone.id]
        selected = reading.occupied if activation_mode == "vision_press" else (
            selection is not None and selection.control_id == zone.id
        )
        color = tuple(int(value) for value in zone.color_bgr)
        thickness = 5 if selected else 2

        if reading.occupied:
            overlay = canvas.copy()
            cv2.rectangle(overlay, (x0, y0), (x1, y1), color, -1)
            cv2.addWeighted(overlay, 0.18, canvas, 0.82, 0, canvas)
        cv2.rectangle(canvas, (x0, y0), (x1, y1), color, thickness)
        label = zone.label if activation_mode == "vision_press" else f"{zone.label}  {reading.occupancy * 100:4.1f}%"
        font_scale = 0.58 if activation_mode == "vision_press" else 0.8
        cv2.putText(
            canvas,
            label,
            (x0 + 7, y0 + 28),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            color,
            2,
            cv2.LINE_AA,
        )

    active_labels = [reading.label for reading in snapshot.zones if reading.occupied]
    if activation_mode == "vision_press" and active_labels:
        status = f"PLAYING: {' + '.join(active_labels)}"
        status_color = (80, 245, 170)
    elif activation_mode == "vision_press":
        status = "TOUCH THE SURFACE: PIANO + DRUMS"
        status_color = (235, 235, 235)
    elif snapshot.ambiguous:
        status = "AMBIGUOUS: clear one zone"
        status_color = (30, 30, 255)
    elif selection is not None:
        status = f"SELECTED: {selection.control_id}  |  press CONFIRM"
        status_color = (60, 230, 255)
    else:
        status = "Move a hand/object into ONE zone"
        status_color = (235, 235, 235)

    cv2.rectangle(canvas, (0, 0), (width, 48), (16, 20, 25), -1)
    cv2.putText(canvas, status, (14, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.72, status_color, 2, cv2.LINE_AA)

    success, encoded = cv2.imencode(".jpg", canvas, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
    if not success:
        raise RuntimeError("Could not encode camera frame")
    return encoded.tobytes()
