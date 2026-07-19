/*
  SurfaceOS — Glyph C6 IMU tap node (Modulino Movement / LSM6DSOX)
  Qwiic: SDA=GPIO4, SCL=GPIO5.

  Tap detection: software spike threshold on accel magnitude.
  No hardware register tap config — works reliably across chip variants.

  Serial (115200 USB CDC):
    READY        — booted
    CAL:ok       — IMU found
    CAL:fail     — IMU not found (check cable)
    TAP          — tap detected (magnitude spike above threshold)
    ACCEL:x.xxx  — motion magnitude every 100 ms (for dashboard bar)
*/

#include <Adafruit_LSM6DSOX.h>
#include <Wire.h>

Adafruit_LSM6DSOX imu;

// ── tuning ─────────────────────────────────────────────────────────
// Raise TAP_THRESHOLD if phantom taps fire at rest.
// Lower it if real taps are missed.
constexpr float    TAP_THRESHOLD   = 0.4f;  // g above 1g baseline
constexpr uint32_t TAP_COOLDOWN_MS = 350;   // ignore re-fires within this window
constexpr uint32_t POLL_MS         = 5;     // accel poll rate

static uint32_t lastTapMs   = 0;
static uint32_t lastAccelMs = 0;
static bool     imuReady    = false;

void setup() {
  Serial.begin(115200);
  Wire.begin(4, 5);  // Glyph C6 Qwiic: SDA=GPIO4, SCL=GPIO5
  delay(300);
  Serial.println("READY");

  if (!imu.begin_I2C(0x6A, &Wire)) {
    Serial.println("CAL:fail");
    return;
  }

  imu.setAccelDataRate(LSM6DS_RATE_416_HZ);
  imu.setAccelRange(LSM6DS_ACCEL_RANGE_2_G);

  imuReady = true;
  Serial.println("CAL:ok");
}

void loop() {
  if (!imuReady) { delay(500); return; }

  const uint32_t now = millis();
  if (now - lastAccelMs < POLL_MS) return;
  lastAccelMs = now;

  sensors_event_t accel, gyro, temp;
  imu.getEvent(&accel, &gyro, &temp);

  // Convert m/s² → g
  float ax = accel.acceleration.x / 9.81f;
  float ay = accel.acceleration.y / 9.81f;
  float az = accel.acceleration.z / 9.81f;
  float mag    = sqrtf(ax*ax + ay*ay + az*az);
  float motion = fabsf(mag - 1.0f);  // subtract 1g gravity baseline

  // ── software tap: rising edge above threshold ──────────────────
  if (motion >= TAP_THRESHOLD && (now - lastTapMs) >= TAP_COOLDOWN_MS) {
    lastTapMs = now;
    Serial.println("TAP");
  }

  // ── stream magnitude every 100 ms for dashboard bar ───────────
  static uint32_t lastStreamMs = 0;
  if (now - lastStreamMs >= 100) {
    lastStreamMs = now;
    Serial.print("ACCEL:");
    Serial.println(motion, 3);
  }
}
