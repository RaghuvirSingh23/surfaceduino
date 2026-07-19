#!/usr/bin/env python3
"""SurfaceOS Local Engine — run the full vision pipeline on this Mac.

Why: eliminates USB/ADB frame relay overhead and uses Mac's faster CPU/GPU
for TFLite inference. Typical gain: 8-12 fps → 25-30 fps on Apple Silicon.

Usage
-----
  cd /path/to/surfaceduino
  python3 scripts/local_engine.py [--port 7001] [--camera 0] [--fps 30]

Then click the "Local" toggle in the SurfaceOS UI. Click again to switch back
to Arduino mode without reloading the page.

What's the same
---------------
  - config/surface.json zones, detector settings, activation mode
  - Hand-landmark detection + zone occupancy via BackgroundZoneDetector
  - /state JSON shape the frontend polls
  - MJPEG /stream with zone + fingertip overlay
  - /api/agent-presets and /api/agent/run

What's different
----------------
  - Camera opened locally with OpenCV — no HTTP frame relay
  - No Bridge → no STM32 LED/buzzer feedback
  - Serves at port 7001 with CORS (browser fetches directly)
"""
from __future__ import annotations

import argparse
import copy
import json
import queue
import sys
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "python"))

import cv2  # noqa: E402

from surfaceos.agents import load_presets, run_agent  # noqa: E402
from surfaceos.config import SurfaceConfig, load_config  # noqa: E402
from surfaceos.detector import BackgroundZoneDetector, DetectionSnapshot  # noqa: E402
from surfaceos.events import InteractionEvent  # noqa: E402
from surfaceos.fusion import FusionEngine  # noqa: E402
from surfaceos.renderer import render_overlay  # noqa: E402

CONFIG_PATH  = REPO_ROOT / "config" / "surface.json"
PRESETS_PATH = REPO_ROOT / "config" / "agent_presets.json"


def now_ms() -> int:
    return time.monotonic_ns() // 1_000_000


# ── shared state (mirrors python/main.py RuntimeStore) ──────────────────────

class LocalStore:
    def __init__(self, config: SurfaceConfig) -> None:
        self._lock = threading.Lock()
        self._jpeg: bytes | None = None
        self._events: deque[dict[str, Any]] = deque(maxlen=30)
        self._state: dict[str, Any] = {
            "input_mode": "starting",
            "activation_mode": config.activation_mode,
            "camera": {"status": "starting", "details": {}},
            "bridge": {"status": "local"},
            "detector": {"calibrated": False, "ambiguous": False},
            "candidate": None,
            "fingertips": [],
            "hands": [],
            "zones": [
                {
                    "id": z.id, "label": z.label, "rect": z.rect,
                    "action": z.action, "group": z.group, "sound": z.sound,
                    "occupancy": 0.0, "occupied": False,
                }
                for z in config.zones
            ],
            "buttons": {"confirm": False, "calibrate": False},
            "last_event": None,
        }

    def set_camera(self, status: str, details: dict[str, Any] | None = None) -> None:
        with self._lock:
            self._state["camera"] = {"status": status, "details": details or {}}

    def set_input_mode(self, mode: str) -> None:
        with self._lock:
            self._state["input_mode"] = mode

    def add_event(self, event: InteractionEvent) -> None:
        d = event.to_dict()
        with self._lock:
            self._events.appendleft(d)
            self._state["last_event"] = d

    def set_detection(
        self,
        config: SurfaceConfig,
        snapshot: DetectionSnapshot,
        candidate: str | None,
    ) -> None:
        zone_cfgs = {z.id: z for z in config.zones}
        with self._lock:
            self._state["detector"] = {
                "calibrated": snapshot.calibrated,
                "ambiguous": snapshot.ambiguous and config.activation_mode != "vision_press",
            }
            self._state["candidate"] = candidate
            self._state["fingertips"] = [
                {"x": round(t.x, 4), "y": round(t.y, 4)} for t in snapshot.fingertips
            ]
            self._state["hands"] = [
                {
                    "score": round(h.score, 3),
                    "handedness": "right" if h.handedness >= 0.5 else "left",
                    "points": [
                        {"x": round(float(x), 4), "y": round(float(y), 4)}
                        for x, y in h.landmarks
                    ],
                }
                for h in snapshot.hands
            ]
            self._state["zones"] = [
                {
                    "id": r.id,
                    "label": r.label,
                    "rect": zone_cfgs[r.id].rect,
                    "action": zone_cfgs[r.id].action,
                    "group": zone_cfgs[r.id].group,
                    "sound": zone_cfgs[r.id].sound,
                    "occupancy": round(r.occupancy, 4),
                    "occupied": r.occupied,
                }
                for r in snapshot.zones
            ]

    def set_jpeg(self, jpeg: bytes) -> None:
        with self._lock:
            self._jpeg = jpeg

    def jpeg(self) -> bytes | None:
        with self._lock:
            return self._jpeg

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            s = copy.deepcopy(self._state)
            s["events"] = list(self._events)
            return s


# ── camera + detection loop ──────────────────────────────────────────────────

def camera_loop(
    store: LocalStore,
    config: SurfaceConfig,
    cmd_q: "queue.SimpleQueue[str]",
    camera_index: int,
    fps_target: float,
) -> None:
    detector  = BackgroundZoneDetector(config.detector, config.zones, config.camera.processing_resolution)
    fusion    = FusionEngine(config.detector.stable_ms, config.detector.candidate_timeout_ms)
    zone_cfgs = {z.id: z for z in config.zones}
    active_zone_ids: set[str] = set()

    def publish(event: InteractionEvent) -> None:
        store.add_event(event)
        print(f"  event: {event.kind}  control={event.control_id}", flush=True)

    frame_period = 1.0 / fps_target

    while True:
        store.set_camera("connecting")
        cap: cv2.VideoCapture | None = None
        try:
            cap = cv2.VideoCapture(camera_index, cv2.CAP_AVFOUNDATION)
            if not cap.isOpened():
                raise RuntimeError(f"cannot open camera index {camera_index}")
            cap.set(cv2.CAP_PROP_FRAME_WIDTH,  config.camera.resolution[0])
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.camera.resolution[1])
            cap.set(cv2.CAP_PROP_FPS,          fps_target)
            cap.set(cv2.CAP_PROP_BUFFERSIZE,   1)

            store.set_camera("connected")
            store.set_input_mode(config.activation_mode)
            detector.request_calibration()
            print(
                f"Camera {camera_index} open — target {fps_target:.0f} fps, "
                f"{int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}",
                flush=True,
            )

            frames = 0
            report_at = time.monotonic() + 5.0
            next_at   = time.monotonic()

            while True:
                # drain command queue
                drained = True
                while drained:
                    try:
                        cmd = cmd_q.get_nowait()
                        if cmd == "calibrate":
                            active_zone_ids.clear()
                            fusion.clear_selection()
                            detector.request_calibration()
                            print("recalibration requested", flush=True)
                        elif cmd == "confirm":
                            publish(fusion.confirm(source="web.ui", timestamp_ms=now_ms()))
                        elif cmd == "tap":
                            publish(fusion.confirm(source="glyph.ir", timestamp_ms=now_ms()))
                    except queue.Empty:
                        drained = False

                delay = next_at - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
                next_at = max(next_at + frame_period, time.monotonic())

                ok, frame = cap.read()
                if not ok or frame is None:
                    raise RuntimeError("frame read failed")

                ts       = now_ms()
                snapshot = detector.analyze(frame)

                if config.activation_mode == "vision_press":
                    current  = {r.id for r in snapshot.zones if r.occupied}
                    readings = {r.id: r for r in snapshot.zones}
                    if snapshot.calibrated_now:
                        active_zone_ids.clear()
                        print("Background captured. SurfaceOS local ready.", flush=True)
                    else:
                        for cid in current - active_zone_ids:
                            z = zone_cfgs[cid]
                            publish(fusion.activate(
                                control_id=cid,
                                source="camera.zone",
                                timestamp_ms=ts,
                                confidence=min(
                                    1.0,
                                    readings[cid].occupancy / max(config.detector.press_ratio * 2.0, 0.01),
                                ),
                                metadata={
                                    "input_mode": "vision_press",
                                    "group": z.group,
                                    "sound": z.sound,
                                    "action": z.action,
                                },
                            ))
                        active_zone_ids.clear()
                        active_zone_ids.update(current)
                    fusion.clear_selection()
                else:
                    fusion.update_selection(snapshot.candidate_id, snapshot.candidate_confidence, ts)

                store.set_detection(config, snapshot, fusion.selection.control_id if fusion.selection else None)
                store.set_jpeg(render_overlay(
                    frame=frame,
                    zones=config.zones,
                    snapshot=snapshot,
                    selection=fusion.selection,
                    activation_mode=config.activation_mode,
                    jpeg_quality=config.camera.jpeg_quality,
                ))

                frames += 1
                now = time.monotonic()
                if now >= report_at:
                    elapsed = now - (report_at - 5.0)
                    print(f"  {frames / elapsed:.1f} fps", flush=True)
                    frames = 0
                    report_at = now + 5.0

        except Exception as exc:
            store.set_camera("error", {"reason": str(exc)})
            print(f"camera error: {exc}; retrying in 2s", file=sys.stderr, flush=True)
            time.sleep(2.0)
        finally:
            if cap is not None:
                cap.release()


# ── HTTP handler ─────────────────────────────────────────────────────────────

def _make_handler(store: LocalStore, presets: dict[str, Any], cmd_q: "queue.SimpleQueue[str]"):

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass  # suppress access log

        def _send_cors(self) -> None:
            self.send_header("Access-Control-Allow-Origin",  "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

        def _json(self, data: Any, status: int = 200) -> None:
            body = json.dumps(data).encode()
            self.send_response(status)
            self._send_cors()
            self.send_header("Content-Type",   "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self) -> None:
            self.send_response(204)
            self._send_cors()
            self.end_headers()

        def do_GET(self) -> None:
            path = self.path.split("?")[0]

            if path == "/state":
                self._json(store.snapshot())

            elif path == "/stream":
                self.send_response(200)
                self._send_cors()
                self.send_header("Content-Type",  "multipart/x-mixed-replace; boundary=frame")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                try:
                    while True:
                        jpeg = store.jpeg()
                        if jpeg is None:
                            time.sleep(0.05)
                            continue
                        self.wfile.write(
                            b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
                        )
                        time.sleep(0.033)  # ~30 fps cap on stream output
                except (BrokenPipeError, ConnectionResetError):
                    pass

            elif path == "/api/agent-presets":
                self._json(presets)

            else:
                self.send_error(404)

        def do_POST(self) -> None:
            path   = self.path.split("?")[0]
            length = int(self.headers.get("Content-Length", 0))
            body   = self.rfile.read(length) if length else b""

            if path in ("/confirm", "/calibrate", "/ingest/tap"):
                cmd_map = {"/confirm": "confirm", "/calibrate": "calibrate", "/ingest/tap": "tap"}
                cmd_q.put(cmd_map[path])
                self._json({"queued": True}, 202)

            elif path == "/api/agent/run":
                try:
                    req       = json.loads(body)
                    preset_id = req.get("preset_id", "")
                    tile_id   = req.get("tile_id", "")
                    preset    = next((p for p in presets.get("presets", []) if p["id"] == preset_id), None)
                    if preset is None:
                        self.send_error(404, f"preset {preset_id!r} not found")
                        return
                    tile = next((t for t in preset.get("tiles", []) if t["id"] == tile_id), None)
                    if tile is None:
                        self.send_error(404, f"tile {tile_id!r} not found")
                        return
                    data = run_agent(tile.get("agent", {}))
                    self._json({"tile_id": tile_id, "preset_id": preset_id, "data": data, "updated_at": now_ms()})
                except Exception as exc:
                    self.send_error(500, str(exc))

            else:
                self.send_error(404)

    return Handler


# ── entry point ──────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="SurfaceOS Local Engine — vision pipeline on this Mac")
    ap.add_argument("--port",   type=int,   default=7001, help="HTTP port (default: 7001)")
    ap.add_argument("--camera", type=int,   default=0,    help="OpenCV camera index (default: 0)")
    ap.add_argument("--fps",    type=float, default=30.0, help="Target camera FPS (default: 30)")
    args = ap.parse_args()

    config  = load_config(CONFIG_PATH)
    presets = load_presets(PRESETS_PATH)
    store   = LocalStore(config)
    cmd_q: queue.SimpleQueue[str] = queue.SimpleQueue()

    threading.Thread(
        target=camera_loop,
        args=(store, config, cmd_q, args.camera, args.fps),
        daemon=True,
        name="camera",
    ).start()

    handler = _make_handler(store, presets, cmd_q)
    server  = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    print(
        f"\nSurfaceOS Local Engine\n"
        f"  http://127.0.0.1:{args.port}   camera={args.camera}  target={args.fps:.0f} fps\n"
        f"  Click 'Local' in the SurfaceOS UI header to connect.\n",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
