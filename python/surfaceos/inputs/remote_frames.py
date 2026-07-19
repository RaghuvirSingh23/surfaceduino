from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class RemoteFrame:
    sequence: int
    jpeg: bytes
    received_at_ms: int
    source: str
    host_sequence: str | None


class RemoteFrameInbox:
    """A thread-safe, latest-frame-only inbox with explicit backpressure."""

    def __init__(self, max_jpeg_bytes: int):
        self.max_jpeg_bytes = max_jpeg_bytes
        self._lock = threading.Lock()
        self._pending: RemoteFrame | None = None
        self._sequence = 0
        self._accepted = 0
        self._replaced = 0
        self._decode_errors = 0
        self._last_received_at_ms: int | None = None
        self._arrival_times: deque[int] = deque(maxlen=30)

    def put(
        self,
        jpeg: bytes,
        received_at_ms: int,
        source: str = "mac",
        host_sequence: str | None = None,
    ) -> tuple[int, bool]:
        if not jpeg:
            raise ValueError("empty frame")
        if len(jpeg) > self.max_jpeg_bytes:
            raise ValueError("frame too large")
        if not (jpeg.startswith(b"\xff\xd8") and jpeg.endswith(b"\xff\xd9")):
            raise ValueError("invalid JPEG")

        with self._lock:
            replaced = self._pending is not None
            self._sequence += 1
            self._accepted += 1
            self._replaced += int(replaced)
            self._last_received_at_ms = received_at_ms
            self._arrival_times.append(received_at_ms)
            self._pending = RemoteFrame(
                sequence=self._sequence,
                jpeg=jpeg,
                received_at_ms=received_at_ms,
                source=source,
                host_sequence=host_sequence,
            )
            return self._sequence, replaced

    def take_latest(self) -> RemoteFrame | None:
        with self._lock:
            frame = self._pending
            self._pending = None
            return frame

    def record_decode_error(self) -> None:
        with self._lock:
            self._decode_errors += 1

    def stats(self, timestamp_ms: int) -> dict[str, int | float | bool | None]:
        with self._lock:
            age_ms = None
            if self._last_received_at_ms is not None:
                age_ms = max(0, timestamp_ms - self._last_received_at_ms)

            fps = 0.0
            if len(self._arrival_times) >= 2:
                span_ms = self._arrival_times[-1] - self._arrival_times[0]
                if span_ms > 0:
                    fps = (len(self._arrival_times) - 1) * 1000.0 / span_ms

            return {
                "accepted": self._accepted,
                "replaced": self._replaced,
                "decode_errors": self._decode_errors,
                "pending": self._pending is not None,
                "last_sequence": self._sequence or None,
                "age_ms": age_ms,
                "fps": round(fps, 1),
            }


def decode_jpeg(jpeg: bytes, max_resolution: tuple[int, int]) -> np.ndarray:
    encoded = np.frombuffer(jpeg, dtype=np.uint8)
    frame = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("JPEG decode failed")

    max_width, max_height = max_resolution
    height, width = frame.shape[:2]
    if width > max_width or height > max_height:
        raise ValueError(
            f"frame resolution {width}x{height} exceeds {max_width}x{max_height}"
        )
    return frame
