# SurfaceOS MVP

SurfaceOS turns two regions of an ordinary surface into controls. The Logitech C270 selects a region; a physical button confirms the action. Vision and the web UI run locally on the Arduino UNO Q's Debian processor, while its STM32 microcontroller debounces buttons and drives immediate LED feedback.

This first version deliberately detects **occupancy/hover, not physical touch**. When the Modulino Movement sensor arrives, its impact signal can become a second confirmation source without changing the vision or event API.

## What works in this milestone

- Two camera-defined regions: `zone_left` and `zone_right`
- Lightweight OpenCV background subtraction at 320×240 processing resolution
- D2 physical **CONFIRM** button
- D3 physical **CALIBRATE** button
- Linux ↔ STM32 communication through Arduino RouterBridge
- Live on-board web UI at `http://<board-name>.local:7000`
- Stable `surfaceos.event.v1` events for future agent, MIDI, robot and app integrations
- Disabled-by-default seam for the future Movement sensor
- Camera-optional fallback: if no C270 is attached, D2 activates ONE and D3 activates TWO

## Camera connection — an extra part is required

The C270 has USB-A and the UNO Q has one USB-C port. The kit's USB-C-to-C cable alone cannot host the camera. Use a **powered USB-C hub with USB-A and PD pass-through**, plus a **5 V / 3 A USB-C supply**:

```text
5 V / 3 A supply ───────> hub PD input
C270 USB-A ─────────────> hub USB-A port
hub upstream USB-C ─────> UNO Q USB-C port
```

Once the hub occupies the UNO Q port, deploy through Arduino App Lab's **Network target over Wi-Fi**. Arduino's own [USB-camera example](https://github.com/arduino/app-bricks-examples/tree/main/examples/platform_unoq/video-face-detection) requires this same powered-hub setup.

Full instructions: [camera connection](docs/camera-connection.md).

## Wire the two buttons

Power the board down first.

```text
D2 ─── CONFIRM button ─── GND
D3 ─── CALIBRATE button ─ GND
```

With the camera connected, D2 confirms the selected visual zone and D3 recalibrates
the background. Without the camera, the app stays alive in direct-button mode: D2
activates `zone_left` (ONE) and D3 activates `zone_right` (TWO). It retries the USB
camera automatically every three seconds.

The sketch uses `INPUT_PULLUP`, so no external button resistors are needed. Put each four-legged tactile switch across the breadboard's centre gap; use opposite sides of the switch.

Do **not** connect the loose red/blue LEDs yet: the kit list contains no current-limiting resistors. This MVP uses the UNO Q's built-in RGB LED. See [wiring](docs/wiring.md).

## Run it on the UNO Q

1. Use the kit's USB-C data cable for initial board setup, updates and Wi-Fi configuration in [Arduino App Lab](https://docs.arduino.cc/software/app-lab/).
2. Before this project, run App Lab's built-in **Face Detector on Camera** example once. That isolates hub, power and C270 problems from our code.
3. Disconnect the laptop cable. Connect the powered hub and camera as shown above.
4. Select the UNO Q **Network** target in App Lab.
5. Open/import this repository as an App Lab app and press **Run**. The standard layout is `app.yaml`, `python/`, `sketch/` and `assets/`.
6. Open `http://<board-name>.local:7000` if the browser does not open automatically.
7. Clear both zones and press D3, or click **Capture background**.
8. Put one hand/object into exactly one region. Wait for `SELECTED`, then press D2.

The first frame is automatically treated as an empty background. D3 recaptures it whenever lighting or camera position changes.

Generate an optional A4 control sheet:

```bash
python3 scripts/generate_surface.py
```

The output is `printables/two-zone-surface.png`. You can also draw two large boxes on plain paper; the web overlay defines the actual active regions.

## Local verification

The hardware-neutral detector and fusion logic can be tested on a laptop:

```bash
./scripts/test.sh
```

On the UNO Q's Debian side, probe a V4L camera directly:

```bash
python3 scripts/probe_camera.py --device /dev/video0 --frames 120
```

Useful board checks:

```bash
lsusb
ls -l /dev/video* /dev/v4l/by-id/*
v4l2-ctl --list-devices
```

## Event contract

Every successful input becomes the same message, regardless of whether confirmation came from a button, dwell, Hall sensor or future impact sensor:

```json
{
  "schema": "surfaceos.event.v1",
  "sequence": 12,
  "source": "mcu.button",
  "kind": "control.activate",
  "control_id": "zone_left",
  "value": 1,
  "timestamp_ms": 8172312,
  "confidence": 0.91,
  "metadata": {"selected_for_ms": 426}
}
```

Architecture and extension points are documented in [architecture](docs/architecture.md).
