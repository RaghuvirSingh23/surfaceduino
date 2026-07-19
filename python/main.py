from __future__ import annotations

import copy
import queue
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from arduino.app_bricks.web_ui import WebUI
from arduino.app_peripherals.camera import Camera
from arduino.app_utils import App, Bridge, Logger

from surfaceos.config import SurfaceConfig, load_config
from surfaceos.detector import BackgroundZoneDetector, DetectionSnapshot
from surfaceos.events import InteractionEvent
from surfaceos.fusion import FusionEngine
from surfaceos.inputs.remote_frames import RemoteFrameInbox, decode_jpeg
from surfaceos.renderer import render_overlay


APP_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = APP_ROOT / "config" / "surface.json"

logger = Logger("SurfaceOS")
config: SurfaceConfig = load_config(CONFIG_PATH)
ui = WebUI()


def now_ms() -> int:
    return time.monotonic_ns() // 1_000_000


class RuntimeStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._latest_jpeg: bytes | None = None
        self._events: deque[dict[str, Any]] = deque(maxlen=30)
        self._state: dict[str, Any] = {
            "input_mode": "starting",
            "activation_mode": config.activation_mode,
            "camera": {"status": "starting", "details": {}},
            "bridge": {"status": "starting"},
            "detector": {"calibrated": False, "ambiguous": False},
            "candidate": None,
            "zones": [
                {
                    "id": zone.id,
                    "label": zone.label,
                    "rect": zone.rect,
                    "action": zone.action,
                    "group": zone.group,
                    "sound": zone.sound,
                    "occupancy": 0.0,
                    "occupied": False,
                }
                for zone in config.zones
            ],
            "buttons": {"confirm": False, "calibrate": False},
            "last_event": None,
        }

    def set_input_mode(self, mode: str) -> None:
        with self._lock:
            self._state["input_mode"] = mode

    def set_camera_status(self, status: str, details: dict[str, Any] | None = None) -> None:
        with self._lock:
            self._state["camera"] = {"status": status, "details": details or {}}

    def set_bridge_status(self, status: str) -> None:
        with self._lock:
            self._state["bridge"] = {"status": status}

    def set_button(self, control: str, pressed: bool) -> None:
        with self._lock:
            self._state["buttons"][control] = pressed

    def set_detection(self, snapshot: DetectionSnapshot, candidate: str | None) -> None:
        zone_configs = {zone.id: zone for zone in config.zones}
        with self._lock:
            self._state["detector"] = {
                "calibrated": snapshot.calibrated,
                "ambiguous": snapshot.ambiguous and config.activation_mode != "vision_press",
            }
            self._state["candidate"] = candidate
            self._state["zones"] = [
                {
                    "id": reading.id,
                    "label": reading.label,
                    "rect": zone_configs[reading.id].rect,
                    "action": zone_configs[reading.id].action,
                    "group": zone_configs[reading.id].group,
                    "sound": zone_configs[reading.id].sound,
                    "occupancy": round(reading.occupancy, 4),
                    "occupied": reading.occupied,
                }
                for reading in snapshot.zones
            ]

    def add_event(self, event: InteractionEvent) -> None:
        payload = event.to_dict()
        with self._lock:
            self._events.appendleft(payload)
            self._state["last_event"] = payload

    def set_jpeg(self, jpeg: bytes) -> None:
        with self._lock:
            self._latest_jpeg = jpeg

    def jpeg(self) -> bytes | None:
        with self._lock:
            return self._latest_jpeg

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            payload = copy.deepcopy(self._state)
            payload["events"] = list(self._events)
            return payload


store = RuntimeStore()
commands: queue.SimpleQueue[tuple[str, str, bool, int]] = queue.SimpleQueue()
detector = BackgroundZoneDetector(config.detector, config.zones, config.camera.processing_resolution)
fusion = FusionEngine(config.detector.stable_ms, config.detector.candidate_timeout_ms)
remote_inbox = RemoteFrameInbox(config.camera.max_jpeg_bytes)
camera: Camera | None = None
camera_retry_at_ms = 0
last_camera_error: str | None = None
vision_active = False
last_good_remote_frame_ms: int | None = None
active_zone_ids: set[str] = set()
CAMERA_RETRY_MS = 3_000


def on_camera_status(status: str, details: dict[str, Any]) -> None:
    store.set_camera_status(status, details)


def on_hardware_event(control: str, pressed: bool, sequence: int) -> None:
    """Bridge callback. Queue only; camera state stays on the main loop."""
    commands.put((str(control), "mcu.button", bool(pressed), int(sequence)))


def enqueue_ui_command(control: str) -> dict[str, Any]:
    commands.put((control, "web.debug", True, now_ms()))
    commands.put((control, "web.debug", False, now_ms()))
    return {"queued": True, "control": control}


def state_api() -> dict[str, Any]:
    return store.snapshot()


async def ingest_frame(request: Request) -> JSONResponse:
    """Accept one Mac-captured JPEG and atomically replace any pending frame."""
    media_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if media_type != "image/jpeg":
        raise HTTPException(status_code=415, detail="expected image/jpeg")

    declared_length = request.headers.get("content-length")
    if declared_length:
        try:
            if int(declared_length) > config.camera.max_jpeg_bytes:
                raise HTTPException(status_code=413, detail="frame too large")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid content-length") from exc

    payload = bytearray()
    async for chunk in request.stream():
        if len(payload) + len(chunk) > config.camera.max_jpeg_bytes:
            raise HTTPException(status_code=413, detail="frame too large")
        payload.extend(chunk)

    try:
        sequence, replaced = remote_inbox.put(
            bytes(payload),
            now_ms(),
            source=request.headers.get("x-surfaceos-camera", "mac"),
            host_sequence=request.headers.get("x-frame-seq"),
        )
    except ValueError as exc:
        status_code = 413 if "too large" in str(exc) else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    return JSONResponse(
        {"accepted": True, "sequence": sequence, "replaced": replaced},
        status_code=202,
    )


def video_frames():
    while True:
        jpeg = store.jpeg()
        if jpeg is None:
            time.sleep(0.1)
            continue
        yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
        time.sleep(0.06)


def video_stream() -> StreamingResponse:
    return StreamingResponse(video_frames(), media_type="multipart/x-mixed-replace; boundary=frame")


def feedback_code(event: InteractionEvent) -> int:
    if event.kind != "control.activate":
        return -1
    group = event.metadata.get("group")
    if group == "piano":
        return 1
    if group == "drum":
        return 2
    return 3


def publish_event(event: InteractionEvent) -> None:
    store.add_event(event)
    logger.info(
        f"{event.kind} control={event.control_id} source={event.source} "
        f"confidence={event.confidence:.2f} metadata={event.metadata}"
    )
    try:
        Bridge.notify("surfaceos_feedback", feedback_code(event))
    except Exception as exc:
        store.set_bridge_status(f"feedback error: {exc}")


def process_commands(timestamp_ms: int) -> None:
    while True:
        try:
            control, source, pressed, _sequence = commands.get_nowait()
        except queue.Empty:
            break

        store.set_button(control, pressed)
        if not pressed:
            continue

        if not vision_active:
            direct_buttons = config.inputs.get("fallback_direct_buttons", {})
            control_id = direct_buttons.get(control)
            if control_id:
                publish_event(fusion.activate_direct(str(control_id), source, timestamp_ms))
            continue

        if control == config.inputs.get("confirm_button", "confirm"):
            if config.activation_mode == "vision_press":
                zone = config.zones[0]
                publish_event(
                    fusion.activate(
                        zone.id,
                        source,
                        timestamp_ms,
                        metadata={
                            "input_mode": "physical_test",
                            "group": zone.group,
                            "sound": zone.sound,
                            "action": zone.action,
                        },
                    )
                )
            else:
                publish_event(fusion.confirm(source=source, timestamp_ms=timestamp_ms))
        elif control == config.inputs.get("calibrate_button", "calibrate"):
            active_zone_ids.clear()
            fusion.clear_selection()
            detector.request_calibration()
            logger.info(f"Background recalibration requested by {source}")


ui.expose_api("GET", "/state", state_api)
ui.expose_api("GET", "/stream", video_stream)
ui.expose_api("POST", "/ingest/frame", ingest_frame)
ui.expose_api("POST", "/confirm", lambda: enqueue_ui_command("confirm"))
ui.expose_api("POST", "/calibrate", lambda: enqueue_ui_command("calibrate"))

try:
    Bridge.provide("surfaceos_hardware_event", on_hardware_event)
    store.set_bridge_status("ready")
except RuntimeError as exc:
    logger.warning(f"Could not register hardware event route yet: {exc}")
    store.set_bridge_status(f"registration error: {exc}")


def close_camera(reason: str) -> None:
    global camera, camera_retry_at_ms, vision_active
    active_camera = camera
    camera = None
    if active_camera is not None:
        try:
            active_camera.__exit__(None, None, None)
        except Exception as exc:
            logger.warning(f"Camera cleanup failed: {exc}")
    camera_retry_at_ms = now_ms() + CAMERA_RETRY_MS
    vision_active = False
    active_zone_ids.clear()
    store.set_camera_status("unavailable", {"reason": reason, "retry_ms": CAMERA_RETRY_MS})
    store.set_input_mode("direct_buttons")


def connect_camera(timestamp_ms: int) -> None:
    """Connect the USB camera if present; otherwise leave both buttons useful."""
    global camera, camera_retry_at_ms, last_camera_error, vision_active
    if config.camera.transport != "local_usb":
        return
    if camera is not None or timestamp_ms < camera_retry_at_ms:
        return

    candidate: Camera | None = None
    try:
        candidate = Camera(
            config.camera.source,
            resolution=config.camera.resolution,
            fps=config.camera.fps,
            codec=config.camera.codec,
        )
        candidate.on_status_changed(on_camera_status)
        candidate.__enter__()
    except Exception as exc:
        if candidate is not None:
            try:
                candidate.__exit__(None, None, None)
            except Exception:
                pass
        camera_retry_at_ms = timestamp_ms + CAMERA_RETRY_MS
        store.set_camera_status(
            "unavailable",
            {"reason": str(exc), "retry_ms": CAMERA_RETRY_MS},
        )
        store.set_input_mode("direct_buttons")
        error_text = str(exc)
        if error_text != last_camera_error:
            logger.warning(f"USB camera unavailable; using D2/D3 direct mode: {error_text}")
            last_camera_error = error_text
        return

    camera = candidate
    last_camera_error = None
    vision_active = True
    store.set_input_mode(config.activation_mode)
    logger.info(f"USB camera connected; using {config.activation_mode} mode")


def process_vision_frame(frame: Any, timestamp_ms: int) -> None:
    snapshot = detector.analyze(frame)
    if config.activation_mode == "vision_press":
        zone_configs = {zone.id: zone for zone in config.zones}
        current_zone_ids = {reading.id for reading in snapshot.zones if reading.occupied}
        readings = {reading.id: reading for reading in snapshot.zones}
        if snapshot.calibrated_now:
            active_zone_ids.clear()
        else:
            for control_id in current_zone_ids - active_zone_ids:
                zone = zone_configs[control_id]
                publish_event(
                    fusion.activate(
                        control_id=control_id,
                        source="camera.zone",
                        timestamp_ms=timestamp_ms,
                        confidence=min(
                            1.0,
                            readings[control_id].occupancy / max(config.detector.press_ratio * 2.0, 0.01),
                        ),
                        metadata={
                            "input_mode": "vision_press",
                            "group": zone.group,
                            "sound": zone.sound,
                            "action": zone.action,
                        },
                    )
                )
            active_zone_ids.clear()
            active_zone_ids.update(current_zone_ids)
        fusion.clear_selection()
    else:
        fusion.update_selection(snapshot.candidate_id, snapshot.candidate_confidence, timestamp_ms)
    process_commands(timestamp_ms)

    if snapshot.calibrated_now:
        logger.info("Background captured. SurfaceOS is ready.")
        try:
            Bridge.notify("surfaceos_feedback", 3)
        except Exception as exc:
            store.set_bridge_status(f"feedback error: {exc}")

    store.set_detection(snapshot, fusion.selection.control_id if fusion.selection else None)
    store.set_jpeg(
        render_overlay(
            frame=frame,
            zones=config.zones,
            snapshot=snapshot,
            selection=fusion.selection,
            activation_mode=config.activation_mode,
            jpeg_quality=config.camera.jpeg_quality,
        )
    )


def loop_remote_camera(timestamp_ms: int) -> None:
    global vision_active, last_good_remote_frame_ms
    packet = remote_inbox.take_latest()
    if packet is not None:
        try:
            frame = decode_jpeg(packet.jpeg, config.camera.max_resolution)
        except ValueError as exc:
            remote_inbox.record_decode_error()
            store.set_camera_status(
                "decode_error",
                {"transport": "http_push", "reason": str(exc), **remote_inbox.stats(timestamp_ms)},
            )
            process_commands(timestamp_ms)
            return

        if not vision_active:
            fusion.clear_selection()
            active_zone_ids.clear()
            detector.request_calibration()
            logger.info("Mac camera feed connected; calibrating remote surface")

        vision_active = True
        last_good_remote_frame_ms = timestamp_ms
        store.set_input_mode(config.activation_mode)
        store.set_camera_status(
            "streaming",
            {
                "transport": "http_push",
                "source": packet.source,
                "host_sequence": packet.host_sequence,
                "frame_sequence": packet.sequence,
                **remote_inbox.stats(timestamp_ms),
            },
        )
        process_vision_frame(frame, timestamp_ms)
        return

    stats = remote_inbox.stats(timestamp_ms)
    good_frame_age_ms = None
    if last_good_remote_frame_ms is not None:
        good_frame_age_ms = max(0, timestamp_ms - last_good_remote_frame_ms)

    if vision_active and good_frame_age_ms is not None and good_frame_age_ms > config.camera.stale_after_ms:
        vision_active = False
        fusion.clear_selection()
        active_zone_ids.clear()
        store.set_input_mode("direct_buttons")
        logger.warning("Mac camera feed stopped; using D2/D3 direct mode")

    if not vision_active:
        status = "waiting_for_mac" if last_good_remote_frame_ms is None else "stale"
        store.set_camera_status(
            status,
            {
                "transport": "http_push",
                "endpoint": "/ingest/frame",
                "frame_age_ms": good_frame_age_ms,
                **stats,
            },
        )

    process_commands(timestamp_ms)
    time.sleep(0.008)


def loop_local_camera(timestamp_ms: int) -> None:
    connect_camera(timestamp_ms)
    if camera is None:
        process_commands(timestamp_ms)
        time.sleep(0.02)
        return

    try:
        frame = camera.capture()
    except Exception as exc:
        logger.warning(f"USB camera disconnected; returning to direct mode: {exc}")
        close_camera(str(exc))
        process_commands(timestamp_ms)
        return

    if frame is None:
        process_commands(timestamp_ms)
        return

    process_vision_frame(frame, timestamp_ms)


def loop() -> None:
    timestamp_ms = now_ms()
    if config.camera.transport == "http_push":
        loop_remote_camera(timestamp_ms)
    else:
        loop_local_camera(timestamp_ms)


logger.info(f"Starting SurfaceOS with config {CONFIG_PATH}")
if config.camera.transport == "http_push":
    store.set_camera_status(
        "waiting_for_mac",
        {"transport": "http_push", "endpoint": "/ingest/frame"},
    )
    store.set_input_mode("direct_buttons")
    logger.info("Waiting for Mac C270 feed on POST /ingest/frame")
else:
    connect_camera(now_ms())
try:
    App.run(user_loop=loop)
finally:
    if camera is not None:
        close_camera("app stopped")
