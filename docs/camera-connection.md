# Connect the Logitech C270 to the UNO Q

## Required topology

The camera connects to the **Linux processor through USB**, never to GPIO pins.

```text
                           ┌──────── Logitech C270 USB-A
                           │
5 V / 3 A USB-C supply ──> powered USB-C hub ──> UNO Q USB-C
                           │
                           └──────── optional keyboard/display during diagnosis
```

Use a hub with:

- a USB-A data port for the C270;
- a USB-C PD input;
- a USB-C upstream connection to the UNO Q.

Arduino's official UNO Q camera example specifies an externally powered hub and 5 V / 3 A supply. See the [example](https://github.com/arduino/app-bricks-examples/tree/main/examples/platform_unoq/video-face-detection) and [UNO Q hardware documentation](https://docs.arduino.cc/hardware/uno-q).

## Setup sequence

1. Initially connect Mac/PC → UNO Q with the kit USB-C-to-C data cable.
2. In Arduino App Lab, update the board, set its password, join Wi-Fi and note its hostname.
3. Stop the current app and disconnect the data cable.
4. Plug the C270 into the powered hub.
5. Power the hub through its PD port with 5 V / 3 A.
6. Connect the hub's upstream USB-C to the UNO Q.
7. Wait for the UNO Q to finish booting.
8. In App Lab select the board's **Network** target.

The UNO Q must be the USB host. Do not connect the hub's upstream port to the development laptop.

## Smoke test before SurfaceOS

Run Arduino App Lab's **Face Detector on Camera** example. Only continue when its live image is stable. This validates:

- USB role switching;
- hub power delivery;
- the C270 UVC video device;
- App Lab's camera permissions.

The C270 microphone may appear as a separate USB audio device. SurfaceOS never opens it and declares no audio Brick.

## Board-side diagnosis

```bash
lsusb
ls -l /dev/video* /dev/v4l/by-id/*
v4l2-ctl --list-devices
v4l2-ctl -d /dev/video0 --list-formats-ext
python3 scripts/probe_camera.py --device /dev/video0
```

Start with 640×480 MJPEG at 15 FPS on the 2 GB board. The detector downsizes frames to 320×240 internally.
