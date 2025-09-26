/* arduino_1.ino — Arduino controller for NodeMCU1 (logic inputs)
 * Role: receive simple logic-level signals from NodeMCU (ESP) and drive actuators.
 * NodeMCU pin mapping (from node_mcu_1.ino):
 *   D1(GPIO5)  -> servo1 (logic input to Arduino pin 2)
 *   D2(GPIO4)  -> servo2 (logic input to Arduino pin 3)
 *   D5(GPIO14) -> servo3 (logic input to Arduino pin 4)
 *   D6(GPIO12) -> servo4 (logic input to Arduino pin 5)
 *   D7(GPIO13) -> dcmotor1_enable (logic input to Arduino pin 6)
 *
 * NodeMCU acts as orchestrator and only toggles logic lines (HIGH/LOW). Arduino
 * acts as controller: implements actuators, PWM, stepper pulses, etc.
 *
 * Wiring notes:
 *  - Connect NodeMCU GND to Arduino GND.
 *  - NodeMCU outputs (3.3V) are read as HIGH by Arduino digital inputs.
 *  - Use proper drivers for motors; Arduino drives the drivers, not the motors directly.
 */

#include <Arduino.h>
#include <Servo.h>

// -------------------- Configuration --------------------
// Arduino input pins receiving logic from NodeMCU
const uint8_t PIN_IN_SERVO1 = 2; // NodeMCU D1 (GPIO5)
const uint8_t PIN_IN_SERVO2 = 3; // NodeMCU D2 (GPIO4)
const uint8_t PIN_IN_SERVO3 = 4; // NodeMCU D5 (GPIO14)
const uint8_t PIN_IN_SERVO4 = 5; // NodeMCU D6 (GPIO12)
const uint8_t PIN_IN_DC_EN   = 6; // NodeMCU D7 (GPIO13)

// Arduino outputs to actuators (change pins as your hardware requires)
const uint8_t PIN_SERVO1_OUT = 9;  // PWM (Servo)
const uint8_t PIN_SERVO2_OUT = 10; // PWM (Servo)
const uint8_t PIN_SERVO3_OUT = 11; // PWM (Servo)
const uint8_t PIN_SERVO4_OUT = 12; // PWM (Servo)
const uint8_t PIN_DC_PWM     = 3;  // PWM to motor driver enable/speed
const uint8_t PIN_DC_DIR     = 7;  // direction pin for motor driver

// Servo positions (safe defaults)
const uint8_t SERVO_CLOSED = 0;   // degrees
const uint8_t SERVO_OPEN   = 90;  // degrees

// Poll interval
const unsigned long POLL_MS = 20;

// -------------------- State --------------------
Servo servo1, servo2, servo3, servo4;

bool last_in_servo1 = false;
bool last_in_servo2 = false;
bool last_in_servo3 = false;
bool last_in_servo4 = false;
bool last_in_dc    = false;

unsigned long last_poll = 0;

// -------------------- Helpers --------------------
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

	pinMode(PIN_DC_PWM, OUTPUT);
	pinMode(PIN_DC_DIR, OUTPUT);
	analogWrite(PIN_DC_PWM, 0);
	digitalWrite(PIN_DC_DIR, LOW);
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
	if (on) {
		// example: set direction forward and provide PWM
		digitalWrite(PIN_DC_DIR, HIGH);
		analogWrite(PIN_DC_PWM, 200); // ~78%
	} else {
		analogWrite(PIN_DC_PWM, 0);
	}
}

// Read a digital input; NodeMCU actively drives the pin HIGH/LOW.
bool readInput(uint8_t pin) {
	return digitalRead(pin) == HIGH;
}

// -------------------- Setup / Loop --------------------
void setup() {
	Serial.begin(115200);
	delay(50);
	Serial.println("[arduino1] starting controller");

	// configure NodeMCU-driven lines as INPUT (NodeMCU drives the levels)
	pinMode(PIN_IN_SERVO1, INPUT);
	pinMode(PIN_IN_SERVO2, INPUT);
	pinMode(PIN_IN_SERVO3, INPUT);
	pinMode(PIN_IN_SERVO4, INPUT);
	pinMode(PIN_IN_DC_EN,   INPUT);

	setupActuators();

	last_poll = millis();
}

void loop() {
	if (millis() - last_poll < POLL_MS) return;
	last_poll = millis();

	bool in1 = readInput(PIN_IN_SERVO1);
	bool in2 = readInput(PIN_IN_SERVO2);
	bool in3 = readInput(PIN_IN_SERVO3);
	bool in4 = readInput(PIN_IN_SERVO4);
	bool inDc = readInput(PIN_IN_DC_EN);

	if (in1 != last_in_servo1) {
		last_in_servo1 = in1;
		Serial.printf("[in] servo1=%d\n", in1);
		handleServoChange(1, in1);
	}
	if (in2 != last_in_servo2) {
		last_in_servo2 = in2;
		Serial.printf("[in] servo2=%d\n", in2);
		handleServoChange(2, in2);
	}
	if (in3 != last_in_servo3) {
		last_in_servo3 = in3;
		Serial.printf("[in] servo3=%d\n", in3);
		handleServoChange(3, in3);
	}
	if (in4 != last_in_servo4) {
		last_in_servo4 = in4;
		Serial.printf("[in] servo4=%d\n", in4);
		handleServoChange(4, in4);
	}
	if (inDc != last_in_dc) {
		last_in_dc = inDc;
		Serial.printf("[in] dc=%d\n", inDc);
		handleDc(inDc);
	}
}

    