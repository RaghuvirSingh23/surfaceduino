# SurfaceOS MVP

SurfaceOS turns an ordinary table into a camera-defined instrument. The Logitech C270 stays connected to the Mac, which relays compressed video frames over USB. JPEG decode, vision, the web UI and events run on the Arduino UNO Q's Debian processor, while its STM32 microcontroller debounces buttons and drives immediate LED feedback.

This first version deliberately detects **occupancy/hover, not physical touch**. When the Modulino Movement sensor arrives, its impact signal can become a second confirmation source without changing the vision or event API.

## What works in this milestone

- Ten camera-defined instrument regions: six piano keys and four drum pads
- **Fingertip tracking**: OpenCV background subtraction + convexity-defect fingertip extraction at 320×240; a zone fires when a fingertip enters it (not whole-hand occupancy)
- Separate **Piano** and **Drums** screens in a React + Tailwind + shadcn dashboard
- D2 physical **C4 TEST** button
- D3 physical **CALIBRATE** button
- Linux ↔ STM32 communication through Arduino RouterBridge
- Mac C270 relay over a loopback-only ADB tunnel; no powered camera hub required
- Live on-board web UI at `http://<board-name>.local:7000`
- Stable `surfaceos.event.v1` events for future agent, MIDI, robot and app integrations
- Disabled-by-default seam for the future Movement sensor
- Camera-feed fallback: if the Mac relay stops, D2 activates C4 and D3 activates kick
- Browser-synthesized piano/drum audio, clickable layout preview and live-feed fullscreen

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
D2 ─── C4 TEST button ─── GND
D3 ─── CALIBRATE button ─ GND
```

While the Mac feed is live, entering a piano key or drum pad fires that instrument on the rising edge; several zones can play together. D2 is a C4 hardware test and D3 recalibrates the background. If the feed stops, direct-button mode keeps D2 as C4 and maps D3 to kick.

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
7. Move a hand into any piano key or drum pad. A note fires once when the zone becomes occupied; leave and re-enter it to play again.

The first frame is automatically treated as an empty background. D3 recaptures it whenever lighting or camera position changes.

Use the dashboard's **Instrument layout** as the surface guide. It mirrors the normalized regions drawn over the live camera feed and every pad can be clicked to preview its sound.

## Fingertip tracking

The detector isolates the hand with background subtraction, then finds fingertips as the convex extremities flanking the deep valleys between fingers (with a topmost-point fallback for a single extended finger). A zone activates when a tracked fingertip lands inside it, so you can rest a palm on the surface and still press one key. Tune it under `detector` in `config/surface.json`:

- `method`: `"fingertip"` (default) or `"occupancy"` (legacy whole-region trigger)
- `fingertip.min_area_frac`, `fingertip.defect_depth_frac`, `fingertip.finger_angle_deg`, `fingertip.merge_radius_frac`, `fingertip.max_points`

Later, the Modulino Movement / IR sensor can confirm a *tap* on top of the tracked fingertip without changing the vision or event API.

## Frontend (React + Tailwind + shadcn)

The on-board dashboard is a Vite + React + TypeScript app in `frontend/`, built with Tailwind v4 and shadcn-style components. It has a home screen plus **separate Piano and Drums screens** (client-side, no server routes) that share one polling loop and audio engine. Piano and drum audio is synthesized in the browser and only the active screen's instrument plays.

The production build is committed to `assets/`, which the UNO Q `WebUI` brick serves statically. To change the UI, edit `frontend/` and rebuild:

```bash
cd frontend
npm install      # first time only
npm run dev      # local dev; proxies /state, /stream, /confirm, /calibrate to 127.0.0.1:17000
npm run build    # emits assets/index.html + assets/static/* for the board
```

## Local verification

The hardware-neutral detector, fingertip tracker and fusion logic can be tested on a laptop:

```bash
./scripts/test.sh
```

Smoke-test exactly ten relayed frames:

```bash
./scripts/run_mac_camera.sh --max-frames 10
```

## Event contract

Every successful input becomes the same message, regardless of whether it came from a camera zone, button or future sensor:

```json
{
  "schema": "surfaceos.event.v1",
  "sequence": 12,
  "source": "camera.zone",
  "kind": "control.activate",
  "control_id": "piano_c4",
  "value": 1,
  "timestamp_ms": 8172312,
  "confidence": 0.91,
  "metadata": {
    "input_mode": "vision_press",
    "group": "piano",
    "sound": "C4",
    "action": "note:C4"
  }
}
```

Architecture and extension points are documented in [architecture](docs/architecture.md).
