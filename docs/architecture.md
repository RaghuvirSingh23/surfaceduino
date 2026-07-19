# Architecture

The Mac is a capture adapter; all interaction processing remains on the UNO Q:

```text
Logitech C270 → Mac AVFoundation → JPEG POST → ADB tunnel ─────┐
                                                               ▼
UNO Q Debian: latest-frame inbox → decode → zone rising edges ───┐
                                                                 ├→ Fusion → surfaceos.event.v1
UNO Q STM32: D2/D3 → debounce → RouterBridge event ──────────────┘
      ▲                                                          │
      └──────────────── built-in RGB feedback RPC ────────────────┘
```

The Mac never decides what a frame means. It opens video only, resizes to 640×480, JPEG-encodes at a fixed rate and sends frames. The UNO Q owns calibration, foreground detection, zone state, event sequencing, web rendering and physical feedback.

The frame inbox is a single atomic slot shared by the WebUI thread and app loop. A new upload replaces an unprocessed older frame, so latency stays bounded even when the sender is faster than the detector. If valid decoded frames stop for 1.2 seconds, active visual zones are cleared and the two buttons fall back to C4 and kick.

## Current interaction state machine

```text
CLEAR
  → foreground crosses the press threshold
OCCUPIED
  → emit one activation on the rising edge
HELD
  → no repeats while the hand remains inside
  → foreground falls below the release threshold for 2 frames
CLEAR
```

Each of the ten zones has its own gate, so piano chords and simultaneous drums work. Release uses a lower occupancy threshold and more frames than press, preventing boundary flicker.

## Why background subtraction first

It uses OpenCV already present in Arduino App Lab, has no neural-model dependency, fits the 2 GB board and requires no marker or additional sensor. It detects a hand or object entering a region; it does not infer fingertip contact.

The detector is intentionally replaceable. Later input adapters can provide:

- ArUco puck ID, centre and rotation;
- hand pointer plus pinch;
- Hall-key authorization;
- Movement-sensor impact timing.

All resolved inputs emit through the same `FusionEngine.activate(...)`, so outputs and agent integrations never depend on the sensor implementation.

## Movement-sensor extension

`python/surfaceos/inputs/movement.py` is disabled now. When hardware arrives:

1. The STM32 samples acceleration through Qwiic.
2. It high-pass-filters acceleration and sends an impact observation over Bridge.
3. The adapter checks the configured magnitude threshold.
4. A qualifying impact confirms the currently selected camera zone within the configured fusion window.

The public event schema and camera detector remain unchanged.
