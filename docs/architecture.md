# Architecture

The application runs entirely on the two processors of one UNO Q:

```text
Logitech C270
      │ USB/V4L2
      ▼
Debian MPU: Camera → foreground detector → visual selection ─┐
                                                            ├→ Fusion → surfaceos.event.v1
STM32 MCU: D2/D3 → debounce → RouterBridge event ───────────┘
      ▲                                                      │
      └────────────── built-in RGB feedback RPC ─────────────┘
```

The laptop is only a development console. After App Lab deploys the project, camera processing, the web server and button handling continue on the UNO Q.

## Current interaction state machine

```text
CLEAR
  → foreground crosses press threshold for 3 frames
CANDIDATE
  → remains selected for 180 ms
ARMED
  → D2 press while latest observation is under 350 ms old
ACTIVATE
```

If both zones are occupied, confirmation fails closed. Release uses a lower occupancy threshold and more frames than press, preventing boundary flicker.

## Why background subtraction first

It uses OpenCV already present in Arduino App Lab, has no neural-model dependency, fits the 2 GB board and requires no marker or additional sensor. It detects a hand or object entering a region; it does not infer fingertip contact.

The detector is intentionally replaceable. Later input adapters can provide:

- ArUco puck ID, centre and rotation;
- hand pointer plus pinch;
- Hall-key authorization;
- Movement-sensor impact timing.

All confirmation sources call the same `FusionEngine.confirm(...)`, so outputs and agent integrations never depend on the sensor implementation.

## Movement-sensor extension

`python/surfaceos/inputs/movement.py` is disabled now. When hardware arrives:

1. The STM32 samples acceleration through Qwiic.
2. It high-pass-filters acceleration and sends an impact observation over Bridge.
3. The adapter checks the configured magnitude threshold.
4. A qualifying impact confirms the currently selected camera zone within the configured fusion window.

The public event schema and camera detector remain unchanged.
