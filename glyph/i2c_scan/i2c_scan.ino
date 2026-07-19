// I2C scanner — prints every address that responds
// Tries SDA/SCL on the two most common Glyph C6 Qwiic pin pairs
#include <Wire.h>

void scan(int sda, int scl) {
  Wire.end();
  Wire.begin(sda, scl);
  Serial.print("SDA="); Serial.print(sda);
  Serial.print(" SCL="); Serial.print(scl); Serial.print("  →  ");
  bool found = false;
  for (uint8_t addr = 8; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    if (Wire.endTransmission() == 0) {
      Serial.print("0x"); Serial.print(addr, HEX); Serial.print(" ");
      found = true;
    }
  }
  if (!found) Serial.print("(nothing)");
  Serial.println();
}

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println("SCAN");
  scan(6, 7);   // Glyph C6 Qwiic default
  scan(4, 5);   // alternate
  scan(1, 0);   // another common pair
  scan(8, 9);   // another
  Serial.println("DONE");
}

void loop() {}
