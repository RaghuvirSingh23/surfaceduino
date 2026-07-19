# Relay the Logitech C270 from the Mac

The C270 remains plugged into the Mac. SurfaceOS opens only its video interface through OpenCV/AVFoundation; it never opens the built-in microphone.

```text
C270 USB-A ──> Mac (capture + JPEG only)
                    │
                    └── http://127.0.0.1:17000/ingest/frame
                                      │ ADB forward
                                      ▼
UNO Q USB-C <──────────────────── port 7000
```

## Start

With the UNO Q connected over its USB-C data cable and SurfaceOS running:

```bash
./scripts/run_mac_camera.sh
```

The launcher restores ADB forwarding from Mac port 17000 to board port 7000, finds the C270, captures 640×480 video at 12 FPS, JPEG-encodes it and sends frames sequentially. Sequential POSTs plus the board's one-frame inbox provide backpressure without an unbounded queue.

Open the dashboard at `http://127.0.0.1:17000`.

## Useful options

```bash
# Send ten frames and stop
./scripts/run_mac_camera.sh --max-frames 10

# Override camera index if macOS enumeration changes
./scripts/run_mac_camera.sh --camera-index 1

# Lower bandwidth
./scripts/run_mac_camera.sh --fps 8 --jpeg-quality 60
```

OpenCV's AVFoundation index order differs from the order reported by Apple's device-list API on this Mac. The verified OpenCV mapping is C270 index `0` and FaceTime index `1`; the launcher therefore defaults explicitly to index `0`. If the feed disappears, the UNO Q marks it stale after 1.2 seconds, clears the visual selection and returns D2/D3 to direct-button mode. A recovered feed automatically captures a fresh background.
