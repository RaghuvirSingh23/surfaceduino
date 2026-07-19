# MVP wiring

## Buttons

Turn off power before changing breadboard wiring.

| Control | UNO Q pin | Other button side | Behaviour |
|---|---:|---:|---|
| Confirm selected camera zone | D2 | GND | Pressed reads LOW |
| Capture empty background | D3 | GND | Pressed reads LOW |

Both inputs use `INPUT_PULLUP`; do not connect either button to 5 V.

Most tactile switches have four legs arranged as two permanently connected pairs. Place the switch across the breadboard centre gap so pressing it connects the two halves. If a button reads as permanently pressed, rotate it 90 degrees.

```text
UNO Q D2 ───── [ CONFIRM ] ───── UNO Q GND
UNO Q D3 ───── [ CALIBRATE ] ─── UNO Q GND
```

## Feedback LED

The sketch uses the UNO Q's built-in RGB LED:

- blue pulse: zone ONE activated;
- red pulse: zone TWO activated;
- green pulse: background captured;
- magenta pulse: confirmation rejected.

Do not wire the loose 5 mm LEDs directly to GPIO. Obtain 220–330 Ω series resistors first.

## Parts intentionally deferred

- LCD: add after the camera/button path is stable; it will show selected control and action.
- Rotary encoder: future edit-mode zone/action selector.
- Hall sensors and magnets: future physical authorization key.
- IR sensor: future wake/presence input, not XY localization.
- LDRs: future lighting-quality guard.
- Buzzer: future output after confirming whether the supplied part is active or passive.
- Movement sensor: optional impact confirmation through Qwiic when it arrives.
