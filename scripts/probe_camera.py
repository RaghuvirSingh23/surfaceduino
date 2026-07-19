#!/usr/bin/env python3
from __future__ import annotations

import argparse
import time
from pathlib import Path

import cv2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Open a V4L/OpenCV camera and measure delivered frames.")
    parser.add_argument("--device", default="/dev/video0", help="V4L path or integer camera index")
    parser.add_argument("--frames", type=int, default=120)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--fps", type=int, default=15)
    parser.add_argument("--output", default="camera-probe.jpg")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    device: str | int = int(args.device) if str(args.device).isdigit() else args.device
    camera = cv2.VideoCapture(device, cv2.CAP_V4L2 if isinstance(device, str) else cv2.CAP_ANY)
    camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    camera.set(cv2.CAP_PROP_FPS, args.fps)

    if not camera.isOpened():
        print(f"ERROR: could not open {device}")
        return 1

    delivered = 0
    latest = None
    started = time.monotonic()
    for _ in range(args.frames):
        ok, frame = camera.read()
        if ok and frame is not None:
            delivered += 1
            latest = frame
    elapsed = time.monotonic() - started
    camera.release()

    if latest is None:
        print("ERROR: camera opened but delivered no frames")
        return 2

    output = Path(args.output)
    cv2.imwrite(str(output), latest)
    print(f"device={device}")
    print(f"resolution={latest.shape[1]}x{latest.shape[0]}")
    print(f"delivered={delivered}/{args.frames}")
    print(f"measured_fps={delivered / max(elapsed, 0.001):.2f}")
    print(f"snapshot={output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
