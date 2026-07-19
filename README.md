# SurfaceOS MVP

SurfaceOS turns two regions of an ordinary surface into controls. The Logitech C270 stays connected to the Mac, which relays compressed video frames over USB. JPEG decode, vision, the web UI and events run on the Arduino UNO Q's Debian processor, while its STM32 microcontroller debounces buttons and drives immediate LED feedback.

This first version deliberately detects **occupancy/hover, not physical touch**. When the Modulino Movement sensor arrives, its impact signal can become a second confirmation source without changing the vision or event API.

## What works in this milestone

- Two camera-defined regions: `zone_left` and `zone_right`
- Lightweight OpenCV background subtraction at 320×240 processing resolution
- D2 physical **CONFIRM** button
- D3 physical **CALIBRATE** button
- Linux ↔ STM32 communication through Arduino RouterBridge
- Mac C270 relay over a loopback-only ADB tunnel; no powered camera hub required
- Live on-board web UI at `http://<board-name>.local:7000`
- Stable `surfaceos.event.v1` events for future agent, MIDI, robot and app integrations
- Disabled-by-default seam for the future Movement sensor
- Camera-feed fallback: if the Mac relay stops, D2 activates ONE and D3 activates TWO

## Camera connection — keep it on the Mac

No additional hub is needed. Keep both devices connected to the Mac:

```text
C270 USB-A ──> Mac OpenCV ── JPEG POST ──> ADB tunnel ──> UNO Q vision
UNO Q USB-C ───────────────── USB data ─────────────────> Mac
```

The relay opens video only—never the webcam microphone. It sends at most one 640×480 JPEG at a time; the UNO Q discards superseded frames instead of accumulating latency.

Full instructions: [camera connection](docs/camera-connection.md).

## Wire the two buttons

Power the board down first.

```text
D2 ─── CONFIRM button ─── GND
D3 ─── CALIBRATE button ─ GND
```

While the Mac feed is live, D2 confirms the selected visual zone and D3 recalibrates the background. If the feed stops, the app stays alive in direct-button mode: D2 activates `zone_left` (ONE) and D3 activates `zone_right` (TWO).

The sketch uses `INPUT_PULLUP`, so no external button resistors are needed. Put each four-legged tactile switch across the breadboard's centre gap; use opposite sides of the switch.

Do **not** connect the loose red/blue LEDs yet: the kit list contains no current-limiting resistors. This MVP uses the UNO Q's built-in RGB LED. See [wiring](docs/wiring.md).

## Run it on the UNO Q

1. Use the kit's USB-C data cable for initial board setup, updates and Wi-Fi configuration in [Arduino App Lab](https://docs.arduino.cc/software/app-lab/).
2. Keep the C270 plugged into the Mac and the UNO Q plugged in with the USB-C data cable.
3. Open/import this repository as an App Lab app and press **Run**.
4. Start the Mac video relay:

   ```bash
   ./scripts/run_mac_camera.sh
   ```

5. Open `http://127.0.0.1:17000`.
6. Keep the surface clear for the first relayed frame, which captures the background automatically. Press D3 or click **Capture background** to redo it.
7. Put one hand/object into exactly one region. Wait for the selection, then press D2.

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

Smoke-test exactly ten relayed frames:

```bash
./scripts/run_mac_camera.sh --max-frames 10
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
