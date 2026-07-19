#include <Arduino_RouterBridge.h>

namespace {

constexpr uint8_t kConfirmPin = D2;
constexpr uint8_t kCalibratePin = D3;
constexpr unsigned long kDebounceMs = 30;
constexpr unsigned long kFeedbackMs = 280;

constexpr uint8_t kLedRed = LED_BUILTIN;
constexpr uint8_t kLedGreen = LED_BUILTIN + 1;
constexpr uint8_t kLedBlue = LED_BUILTIN + 2;

struct ButtonState {
  uint8_t pin;
  const char* control;
  bool rawPressed;
  bool stablePressed;
  unsigned long changedAt;
};

ButtonState buttons[] = {
  {kConfirmPin, "confirm", false, false, 0},
  {kCalibratePin, "calibrate", false, false, 0},
};

uint32_t eventSequence = 0;
int feedback = 0;
unsigned long feedbackEndsAt = 0;

void setRgb(bool red, bool green, bool blue) {
  // UNO Q built-in RGB channels are active-low.
  digitalWrite(kLedRed, red ? LOW : HIGH);
  digitalWrite(kLedGreen, green ? LOW : HIGH);
  digitalWrite(kLedBlue, blue ? LOW : HIGH);
}

void surfaceosFeedback(int code) {
  feedback = code;
  feedbackEndsAt = millis() + kFeedbackMs;
}

void updateFeedback() {
  if (feedback != 0 && static_cast<long>(millis() - feedbackEndsAt) >= 0) {
    feedback = 0;
  }

  switch (feedback) {
    case 1: setRgb(false, false, true); break;   // zone ONE
    case 2: setRgb(true, false, false); break;   // zone TWO
    case 3: setRgb(false, true, false); break;   // calibrated
    case -1: setRgb(true, false, true); break;   // rejected/error
    default: setRgb(false, false, false); break;
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
  pinMode(kConfirmPin, INPUT_PULLUP);
  pinMode(kCalibratePin, INPUT_PULLUP);

  pinMode(kLedRed, OUTPUT);
  pinMode(kLedGreen, OUTPUT);
  pinMode(kLedBlue, OUTPUT);
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
