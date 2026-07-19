from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CameraConfig:
    transport: str
    source: str
    resolution: tuple[int, int]
    processing_resolution: tuple[int, int]
    max_resolution: tuple[int, int]
    fps: int
    codec: str
    jpeg_quality: int
    stale_after_ms: int
    max_jpeg_bytes: int


@dataclass(frozen=True)
class DetectorConfig:
    pixel_threshold: int
    press_ratio: float
    release_ratio: float
    press_frames: int
    release_frames: int
    stable_ms: int
    candidate_timeout_ms: int
    adapt_rate: float
    method: str
    fingertip_min_area_frac: float
    fingertip_defect_depth_frac: float
    fingertip_finger_angle_deg: float
    fingertip_merge_radius_frac: float
    fingertip_max_points: int
    landmark_palm_score: float
    landmark_score: float
    landmark_max_hands: int
    landmark_detect_period: int
    landmark_num_threads: int


@dataclass(frozen=True)
class ZoneConfig:
    id: str
    label: str
    rect: tuple[float, float, float, float]
    action: str
    group: str
    sound: str
    color_bgr: tuple[int, int, int]


@dataclass(frozen=True)
class SurfaceConfig:
    camera: CameraConfig
    detector: DetectorConfig
    activation_mode: str
    dwell_ms: int
    zones: tuple[ZoneConfig, ...]
    inputs: dict[str, Any]


def _pair(value: list[int], name: str) -> tuple[int, int]:
    if len(value) != 2 or any(int(item) <= 0 for item in value):
        raise ValueError(f"{name} must contain two positive integers")
    return int(value[0]), int(value[1])


def load_config(path: str | Path) -> SurfaceConfig:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    camera = raw["camera"]
    detector = raw["detector"]
    activation = raw["activation"]

    zones: list[ZoneConfig] = []
    seen_ids: set[str] = set()
    for item in raw["zones"]:
        rect = tuple(float(value) for value in item["rect"])
        if len(rect) != 4:
            raise ValueError(f"Zone {item['id']} rect must have four values")
        x0, y0, x1, y1 = rect
        if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
            raise ValueError(f"Zone {item['id']} rect must be normalized and ordered")
        if item["id"] in seen_ids:
            raise ValueError(f"Duplicate zone id: {item['id']}")
        seen_ids.add(item["id"])
        zones.append(
            ZoneConfig(
                id=item["id"],
                label=item.get("label", item["id"]),
                rect=rect,
                action=item.get("action", item["id"]),
                group=item.get("group", "control"),
                sound=item.get("sound", item["id"]),
                color_bgr=tuple(int(value) for value in item.get("color_bgr", [255, 255, 255])),
            )
        )

    if not zones:
        raise ValueError("At least one camera zone is required")
    if detector["release_ratio"] >= detector["press_ratio"]:
        raise ValueError("release_ratio must be lower than press_ratio for hysteresis")

    detector_method = str(detector.get("method", "landmark"))
    if detector_method not in {"landmark", "fingertip", "occupancy"}:
        raise ValueError("detector.method must be landmark, fingertip or occupancy")
    fingertip = detector.get("fingertip", {})
    landmark = detector.get("landmark", {})

    transport = str(camera.get("transport", "http_push"))
    if transport not in {"http_push", "local_usb"}:
        raise ValueError("camera.transport must be http_push or local_usb")
    stale_after_ms = int(camera.get("stale_after_ms", 1200))
    max_jpeg_bytes = int(camera.get("max_jpeg_bytes", 524288))
    if stale_after_ms <= 0 or max_jpeg_bytes <= 0:
        raise ValueError("camera stale timeout and JPEG size limit must be positive")

    activation_mode = str(activation.get("mode", "physical_confirm"))
    if activation_mode not in {"physical_confirm", "vision_press"}:
        raise ValueError("activation.mode must be physical_confirm or vision_press")

    return SurfaceConfig(
        camera=CameraConfig(
            transport=transport,
            source=str(camera.get("source", "0")),
            resolution=_pair(camera["resolution"], "camera.resolution"),
            processing_resolution=_pair(camera["processing_resolution"], "camera.processing_resolution"),
            max_resolution=_pair(camera.get("max_resolution", [1280, 720]), "camera.max_resolution"),
            fps=int(camera["fps"]),
            codec=str(camera.get("codec", "MJPG")),
            jpeg_quality=int(camera.get("jpeg_quality", 72)),
            stale_after_ms=stale_after_ms,
            max_jpeg_bytes=max_jpeg_bytes,
        ),
        detector=DetectorConfig(
            pixel_threshold=int(detector["pixel_threshold"]),
            press_ratio=float(detector["press_ratio"]),
            release_ratio=float(detector["release_ratio"]),
            press_frames=int(detector["press_frames"]),
            release_frames=int(detector["release_frames"]),
            stable_ms=int(detector["stable_ms"]),
            candidate_timeout_ms=int(detector["candidate_timeout_ms"]),
            adapt_rate=float(detector.get("adapt_rate", 0.0)),
            method=detector_method,
            fingertip_min_area_frac=float(fingertip.get("min_area_frac", 0.010)),
            fingertip_defect_depth_frac=float(fingertip.get("defect_depth_frac", 0.020)),
            fingertip_finger_angle_deg=float(fingertip.get("finger_angle_deg", 90.0)),
            fingertip_merge_radius_frac=float(fingertip.get("merge_radius_frac", 0.030)),
            fingertip_max_points=int(fingertip.get("max_points", 10)),
            landmark_palm_score=float(landmark.get("palm_score", 0.5)),
            landmark_score=float(landmark.get("landmark_score", 0.5)),
            landmark_max_hands=int(landmark.get("max_hands", 2)),
            landmark_detect_period=int(landmark.get("detect_period", 8)),
            landmark_num_threads=int(landmark.get("num_threads", 4)),
        ),
        activation_mode=activation_mode,
        dwell_ms=int(activation.get("dwell_ms", 900)),
        zones=tuple(zones),
        inputs=dict(raw.get("inputs", {})),
    )
