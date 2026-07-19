#include <Arduino_RouterBridge.h>

namespace {

constexpr uint8_t kConfirmPin   = D2;
constexpr uint8_t kCalibratePin = D3;
constexpr uint8_t kBuzzerPin    = D4;   // passive piezo buzzer (D4 → buzzer → GND)

constexpr unsigned long kDebounceMs = 30;
constexpr unsigned long kFeedbackMs = 300;

constexpr uint8_t kLedRed   = LED_BUILTIN;
constexpr uint8_t kLedGreen = LED_BUILTIN + 1;
constexpr uint8_t kLedBlue  = LED_BUILTIN + 2;

// Piano: C4 D4 E4 F4 G4 A4  (codes 1-6)
const uint16_t kPianoFreq[] = {262, 294, 330, 349, 392, 440};

// Drums: kick snare hat tom  (codes 7-10)
const uint16_t kDrumFreq[] = {80,  180, 800, 140};
const uint16_t kDrumDur[]  = {200, 80,  50,  150};

struct ButtonState {
  uint8_t pin;
  const char* control;
  bool rawPressed;
  bool stablePressed;
  unsigned long changedAt;
};

ButtonState buttons[] = {
  {kConfirmPin,   "confirm",   false, false, 0},
  {kCalibratePin, "calibrate", false, false, 0},
};

uint32_t eventSequence = 0;
int feedback = 0;
unsigned long feedbackEndsAt = 0;

void setRgb(bool r, bool g, bool b) {
  // UNO Q built-in RGB is active-low
  digitalWrite(kLedRed,   r ? LOW : HIGH);
  digitalWrite(kLedGreen, g ? LOW : HIGH);
  digitalWrite(kLedBlue,  b ? LOW : HIGH);
}

void surfaceosFeedback(int code) {
  feedback = code;
  feedbackEndsAt = millis() + kFeedbackMs;

  if (code >= 1 && code <= 6) {
    // Piano keys C4–A4: blue LED + note tone
    setRgb(false, false, true);
    tone(kBuzzerPin, kPianoFreq[code - 1], 120);
  } else if (code >= 7 && code <= 10) {
    // Drum pads kick=7 snare=8 hat=9 tom=10
    int i = code - 7;
    if (i == 0)      setRgb(true,  false, false);  // kick  → red
    else if (i == 1) setRgb(true,  true,  true);   // snare → white
    else if (i == 2) setRgb(false, true,  false);  // hat   → green
    else             setRgb(false, true,  true);   // tom   → cyan
    tone(kBuzzerPin, kDrumFreq[i], kDrumDur[i]);
  } else if (code == 11) {
    // Calibrated
    setRgb(false, true, false);
  } else if (code == -1) {
    // Rejected / no selection
    setRgb(true, false, true);
  }
}

void updateFeedback() {
  if (feedback != 0 && static_cast<long>(millis() - feedbackEndsAt) >= 0) {
    feedback = 0;
    setRgb(false, false, false);
  }
}

void publishButton(const ButtonState& button) {
  ++eventSequence;
  Bridge.notify(
    "surfaceos_hardware_event",
    String(button.control),
    button.stablePressed,
    eventSequence
  );
}

void updateButton(ButtonState& button, unsigned long now) {
  const bool pressed = digitalRead(button.pin) == LOW;
  if (pressed != button.rawPressed) {
    button.rawPressed = pressed;
    button.changedAt = now;
  }
  if (button.stablePressed != button.rawPressed && now - button.changedAt >= kDebounceMs) {
    button.stablePressed = button.rawPressed;
    publishButton(button);
  }
}

}  // namespace

void setup() {
  pinMode(kConfirmPin,   INPUT_PULLUP);
  pinMode(kCalibratePin, INPUT_PULLUP);
  pinMode(kBuzzerPin,    OUTPUT);

  pinMode(kLedRed,   OUTPUT);
  pinMode(kLedGreen, OUTPUT);
  pinMode(kLedBlue,  OUTPUT);
  setRgb(false, false, false);

  Bridge.begin();
  Bridge.provide("surfaceos_feedback", surfaceosFeedback);
}

void loop() {
  const unsigned long now = millis();
  for (auto& button : buttons) {
    updateButton(button, now);
  }
  updateFeedback();
}
