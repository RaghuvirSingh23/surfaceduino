#!/usr/bin/env python3
from __future__ import annotations

import argparse
import http.client
import json
import signal
import sys
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

import cv2


STOP_REQUESTED = False


def request_stop(_signum: int, _frame: object) -> None:
    global STOP_REQUESTED
    STOP_REQUESTED = True


def resolve_camera_index(camera_name: str, camera_uid: str, override_index: int | None) -> int:
    if override_index is not None:
        return override_index
    try:
        from AVFoundation import AVCaptureDevice, AVMediaTypeVideo

        devices = list(AVCaptureDevice.devicesWithMediaType_(AVMediaTypeVideo))
        for index, device in enumerate(devices):
            if camera_uid and str(device.uniqueID()) == camera_uid:
                return index
        for index, device in enumerate(devices):
            if camera_name.casefold() in str(device.localizedName()).casefold():
                return index
    except Exception as exc:
        raise RuntimeError(f"could not enumerate macOS video devices: {exc}") from exc
    raise RuntimeError(f"{camera_name!r} was not found; refusing to use another camera")


def open_camera(index: int, width: int, height: int, fps: float) -> cv2.VideoCapture:
    camera = cv2.VideoCapture(index, cv2.CAP_AVFOUNDATION)
    if not camera.isOpened():
        camera.release()
        raise RuntimeError(f"could not open AVFoundation camera index {index}")
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    camera.set(cv2.CAP_PROP_FPS, fps)
    camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return camera


@dataclass
class FrameClient:
    url: str
    timeout: float

    def __post_init__(self) -> None:
        parsed = urlsplit(self.url)
        if parsed.scheme != "http" or not parsed.hostname:
            raise ValueError("feed URL must be an http:// URL")
        self.host = parsed.hostname
        self.port = parsed.port or 80
        self.path = parsed.path or "/"
        if parsed.query:
            self.path += f"?{parsed.query}"
        self.connection: http.client.HTTPConnection | None = None

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def send(self, jpeg: bytes, sequence: int, camera_name: str) -> dict[str, object]:
        if self.connection is None:
            self.connection = http.client.HTTPConnection(self.host, self.port, timeout=self.timeout)
        try:
            self.connection.request(
                "POST",
                self.path,
                body=jpeg,
                headers={
                    "Content-Type": "image/jpeg",
                    "Content-Length": str(len(jpeg)),
                    "X-Frame-Seq": str(sequence),
                    "X-SurfaceOS-Camera": camera_name,
                },
            )
            response = self.connection.getresponse()
            payload = response.read()
            if response.status != 202:
                raise RuntimeError(f"board returned HTTP {response.status}: {payload[:200]!r}")
            return json.loads(payload)
        except Exception:
            self.close()
            raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Push Logitech C270 frames from macOS to SurfaceOS")
    parser.add_argument("--url", default="http://127.0.0.1:17000/ingest/frame")
    parser.add_argument("--camera-name", default="C270")
    parser.add_argument("--camera-uid", default="0x1140000046d0825")
    parser.add_argument("--camera-index", type=int, default=None, help="explicit AVFoundation override")
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--fps", type=float, default=12.0)
    parser.add_argument("--jpeg-quality", type=int, default=72)
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--max-frames", type=int, default=0, help="stop after N accepted frames; 0 runs forever")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.fps <= 0 or not 1 <= args.jpeg_quality <= 100:
        raise SystemExit("fps must be positive and JPEG quality must be between 1 and 100")

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    camera_index = resolve_camera_index(args.camera_name, args.camera_uid, args.camera_index)
    client = FrameClient(args.url, args.timeout)
    sequence = 0
    accepted = 0
    bytes_sent = 0
    report_started = time.monotonic()
    retry_delay = 0.5

    print(
        f"SurfaceOS Mac relay: {args.camera_name} index={camera_index} "
        f"{args.width}x{args.height}@{args.fps:g} -> {args.url}",
        flush=True,
    )

    while not STOP_REQUESTED and (not args.max_frames or accepted < args.max_frames):
        try:
            camera = open_camera(camera_index, args.width, args.height, args.fps)
        except RuntimeError as exc:
            print(f"camera unavailable: {exc}; retrying", file=sys.stderr, flush=True)
            time.sleep(retry_delay)
            retry_delay = min(4.0, retry_delay * 2.0)
            continue

        retry_delay = 0.5
        frame_period = 1.0 / args.fps
        next_frame_at = time.monotonic()
        try:
            while not STOP_REQUESTED and (not args.max_frames or accepted < args.max_frames):
                delay = next_frame_at - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
                next_frame_at = max(next_frame_at + frame_period, time.monotonic())

                ok, frame = camera.read()
                if not ok or frame is None:
                    raise RuntimeError("camera frame read failed")
                if frame.shape[1] != args.width or frame.shape[0] != args.height:
                    frame = cv2.resize(frame, (args.width, args.height), interpolation=cv2.INTER_AREA)

                encoded, jpeg = cv2.imencode(
                    ".jpg",
                    frame,
                    [cv2.IMWRITE_JPEG_QUALITY, args.jpeg_quality],
                )
                if not encoded:
                    raise RuntimeError("JPEG encoding failed")

                sequence += 1
                try:
                    client.send(jpeg.tobytes(), sequence, args.camera_name)
                except Exception as exc:
                    print(f"board unavailable: {exc}; reconnecting", file=sys.stderr, flush=True)
                    time.sleep(0.25)
                    continue

                accepted += 1
                bytes_sent += int(jpeg.size)
                now = time.monotonic()
                elapsed = now - report_started
                if elapsed >= 2.0:
                    print(
                        f"streaming {accepted / elapsed:.1f} fps, "
                        f"{bytes_sent / elapsed / 1024:.0f} KiB/s, accepted={accepted}",
                        flush=True,
                    )
                    accepted = 0 if not args.max_frames else accepted
                    bytes_sent = 0
                    report_started = now
        except RuntimeError as exc:
            print(f"{exc}; reopening camera", file=sys.stderr, flush=True)
            time.sleep(retry_delay)
        finally:
            camera.release()

    client.close()
    print("SurfaceOS Mac relay stopped", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
