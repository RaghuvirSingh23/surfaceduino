/*
  SurfaceOS — Glyph C6 (ESP32-C6) IR tap node
  ---------------------------------------------
  An IR obstacle/proximity module (FC-51 style, digital OUT) watches the surface.
  When a finger descends into the beam we emit "TAP\n" over USB serial.
  The Mac-side glyph_tap_relay.py reads that line and POSTs /ingest/tap
  to the UNO Q, where the FusionEngine combines it with the camera's zone.

  Wiring (see README):
    IR VCC -> Glyph 3V3
    IR GND -> Glyph GND
    IR OUT -> Glyph IO4

  Polarity is NOT hardcoded. At boot we assume the surface is clear and sample
  the idle output level; "finger present" is simply the opposite level. This
  works for active-low AND active-high FC-51 modules with no code change.
  Keep the beam clear during the first ~0.4s after reset (same idea as the
  camera's "first empty frame = background" calibration).
*/

constexpr uint8_t IR_PIN       = 4;    // Glyph IO4
constexpr uint32_t DEBOUNCE_MS = 120;  // ignore re-triggers for this long
constexpr uint32_t REARM_MS    = 40;   // beam must be clear this long to re-arm

int      presentLevel = HIGH;          // set by calibrate(): level that means "finger present"
bool     armed        = true;          // ready to fire the next tap
uint32_t lastTapMs    = 0;
uint32_t clearSinceMs = 0;

bool fingerPresent() {
  return digitalRead(IR_PIN) == presentLevel;
}

// Sample the idle level with the surface clear; "present" is the opposite level.
void calibrate() {
  int highCount = 0;
  for (int i = 0; i < 40; i++) {
    if (digitalRead(IR_PIN) == HIGH) highCount++;
    delay(5);
  }
  const int idleLevel = (highCount > 20) ? HIGH : LOW;   // majority vote
  presentLevel = (idleLevel == HIGH) ? LOW : HIGH;
  Serial.print("CAL idle=");
  Serial.print(idleLevel == HIGH ? 1 : 0);
  Serial.print(" present=");
  Serial.println(presentLevel == HIGH ? 1 : 0);
}

void setup() {
  Serial.begin(115200);
  pinMode(IR_PIN, INPUT);   // FC-51 OUT is push-pull; no pullup needed
  delay(200);               // let USB CDC settle so the host catches the banner
  Serial.println("READY");
  calibrate();              // ~200ms; keep the beam clear during this
  armed = !fingerPresent(); // don't fire a phantom tap if something is already there
}

void loop() {
  const uint32_t now = millis();
  const bool present = fingerPresent();

  // Stream the raw IR state whenever it changes, so the dashboard can show it.
  static int lastReported = -1;
  if ((int)present != lastReported) {
    lastReported = (int)present;
    Serial.println(present ? "IR:1" : "IR:0");
  }

  if (present) {
    clearSinceMs = 0;
    if (armed && (now - lastTapMs) >= DEBOUNCE_MS) {
      Serial.println("TAP");
      lastTapMs = now;
      armed = false;            // one tap per finger-down; re-arm on release
    }
  } else {
    // Beam clear: re-arm once the finger has been gone long enough.
    if (clearSinceMs == 0) clearSinceMs = now;
    if (!armed && (now - clearSinceMs) >= REARM_MS) {
      armed = true;
    }
  }
}
