/* arduino_1.ino — Arduino controller for NodeMCU1 (logic inputs)
 * Role: read simple logic levels from NodeMCU and drive actuators.
 *
 * NodeMCU → Arduino INPUTS (keep your mapping):
 *   D1(GPIO5)  -> Arduino 2  (servo1 in)
 *   D2(GPIO4)  -> Arduino 3  (servo2 in)
 *   D5(GPIO14) -> Arduino 4  (servo3 in)
 *   D6(GPIO12) -> Arduino 5  (servo4 in)
 *   D7(GPIO13) -> Arduino 6  (dc enable in)
 *
 * Arduino OUTPUTS to actuators (you can wire to drivers/servos):
 *   Servo1 out -> 9
 *   Servo2 out -> 10
 *   Servo3 out -> 11
 *   Servo4 out -> 12
 *   DC_EN out  -> 8   (ON/OFF only)
 *   DC_DIR out -> 7   (fixed direction if you need it)
 *
 * Notes:
 * - Common GND between NodeMCU and Arduino.
 * - Arduino drives drivers/servos; NodeMCU only provides logic cues.
 */

#include <Arduino.h>
#include <Servo.h>

// ---------- Inputs from NodeMCU ----------
const uint8_t PIN_IN_SERVO1 = 2;
const uint8_t PIN_IN_SERVO2 = 3;
const uint8_t PIN_IN_SERVO3 = 4;
const uint8_t PIN_IN_SERVO4 = 5;
const uint8_t PIN_IN_DC_EN  = 6;

// ---------- Outputs to actuators ----------
const uint8_t PIN_SERVO1_OUT = 9;
const uint8_t PIN_SERVO2_OUT = 10;
const uint8_t PIN_SERVO3_OUT = 11;
const uint8_t PIN_SERVO4_OUT = 12;

const uint8_t PIN_DC_EN_OUT  = 8;  // ON/OFF enable line to your motor driver
const uint8_t PIN_DC_DIR_OUT = 7;  // optional direction

// ---------- Servo positions ----------
const uint8_t SERVO_CLOSED = 0;    // adjust to your mechanics
const uint8_t SERVO_OPEN   = 90;   // adjust to your mechanics

// ---------- Poll interval ----------
const unsigned long POLL_MS = 20;

// ---------- State ----------
Servo servo1, servo2, servo3, servo4;
bool last_in_servo1 = false;
bool last_in_servo2 = false;
bool last_in_servo3 = false;
bool last_in_servo4 = false;
bool last_in_dc     = false;
unsigned long last_poll = 0;

// ---------- Helpers ----------
void setupActuators() {
  servo1.attach(PIN_SERVO1_OUT);
  servo2.attach(PIN_SERVO2_OUT);
  servo3.attach(PIN_SERVO3_OUT);
  servo4.attach(PIN_SERVO4_OUT);

  // safe positions
  servo1.write(SERVO_CLOSED);
  servo2.write(SERVO_CLOSED);
  servo3.write(SERVO_CLOSED);
  servo4.write(SERVO_CLOSED);

  pinMode(PIN_DC_EN_OUT, OUTPUT);
  pinMode(PIN_DC_DIR_OUT, OUTPUT);
  digitalWrite(PIN_DC_EN_OUT, LOW);   // OFF
  digitalWrite(PIN_DC_DIR_OUT, LOW);  // direction default
}

void handleServoChange(uint8_t idx, bool active) {
  uint8_t pos = active ? SERVO_OPEN : SERVO_CLOSED;
  switch (idx) {
    case 1: servo1.write(pos); break;
    case 2: servo2.write(pos); break;
    case 3: servo3.write(pos); break;
    case 4: servo4.write(pos); break;
  }
}

void handleDc(bool on) {
  // ON/OFF only (you can add PWM later if you add a driver that needs it)
  digitalWrite(PIN_DC_EN_OUT, on ? HIGH : LOW);
}

// Read digital input (NodeMCU drives 0/1)
bool readInput(uint8_t pin) {
  return digitalRead(pin) == HIGH;
}

// ---------- Setup / Loop ----------
void setup() {
  Serial.begin(115200);
  delay(50);
  Serial.println(F("[arduino1] starting controller"));

  pinMode(PIN_IN_SERVO1, INPUT);
  pinMode(PIN_IN_SERVO2, INPUT);
  pinMode(PIN_IN_SERVO3, INPUT);
  pinMode(PIN_IN_SERVO4, INPUT);
  pinMode(PIN_IN_DC_EN,  INPUT);

  setupActuators();

  last_poll = millis();
}

void loop() {
  if (millis() - last_poll < POLL_MS) return;
  last_poll = millis();

  bool in1  = readInput(PIN_IN_SERVO1);
  bool in2  = readInput(PIN_IN_SERVO2);
  bool in3  = readInput(PIN_IN_SERVO3);
  bool in4  = readInput(PIN_IN_SERVO4);
  bool inDc = readInput(PIN_IN_DC_EN);

  if (in1 != last_in_servo1) {
    last_in_servo1 = in1;
    Serial.print(F("[in] servo1=")); Serial.println(in1 ? 1 : 0);
    handleServoChange(1, in1);
  }
  if (in2 != last_in_servo2) {
    last_in_servo2 = in2;
    Serial.print(F("[in] servo2=")); Serial.println(in2 ? 1 : 0);
    handleServoChange(2, in2);
  }
  if (in3 != last_in_servo3) {
    last_in_servo3 = in3;
    Serial.print(F("[in] servo3=")); Serial.println(in3 ? 1 : 0);
    handleServoChange(3, in3);
  }
  if (in4 != last_in_servo4) {
    last_in_servo4 = in4;
    Serial.print(F("[in] servo4=")); Serial.println(in4 ? 1 : 0);
    handleServoChange(4, in4);
  }
  if (inDc != last_in_dc) {
    last_in_dc = inDc;
    Serial.print(F("[in] dc=")); Serial.println(inDc ? 1 : 0);
    handleDc(inDc);
  }
}
