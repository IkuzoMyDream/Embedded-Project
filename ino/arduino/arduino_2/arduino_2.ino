/* arduino_2.ino — Arduino controller for NodeMCU2 (SoftwareSerial communication)
 * Role: Receive commands via SoftwareSerial from NodeMCU and control stepper/servos/pump/DC
 * Communication: NodeMCU sends CSV commands, Arduino responds with "done"
 *
 * Hardware connections:
 *   NodeMCU TX (D6/GPIO12) -> Arduino Pin 2 (RX)
 *   NodeMCU RX (D7/GPIO13) -> Arduino Pin 3 (TX)
 *   GND -> GND
 *   Both devices can be connected to USB separately for programming/monitoring
 *
 * Pin Assignments:
 *   Pins 8,9,10,11 -> NEMA17 Stepper Motor Outputs
 *   Pin 12 -> NEMA17 Control Pin
 *   Pins 2,3 -> TX/RX Communication
 *   Pins 4,5,6 -> IR Sensors 1,2,3
 *   Pin 7 -> DC Motor Enable
 *   Pin A0 -> Servo 1 (Digital output)
 *   Pin A1 -> Servo 2 (Digital output)
 *   Pin A2 -> Pump (Digital output)
 *
 * Serial Protocol:
 *   NodeMCU -> Arduino: "STEP,0/1" or "STEP_EN,0/1" or "SERVO1,0/1" or "SERVO2,0/1" or "PUMP,0/1" or "DC,0/1"
 *   Arduino -> NodeMCU: "done" when operation complete
 *   
 *   Control Scheme:
 *     STEP,0 = Turn Left (Counter-clockwise)
 *     STEP,1 = Turn Right (Clockwise)
 *     STEP_EN,0 = Disable Stepper Motor
 *     STEP_EN,1 = Enable Stepper Motor
 *     SERVO1/2,0/1 = Digital servo control
 *     DC,0/1 = Disable/Enable DC Motor
 *     IR sensors report detection automatically
 */

#include <Arduino.h>
#include <SoftwareSerial.h>

// ---------- Communication pins ----------
const uint8_t PIN_RX = 2;  // Arduino receives from NodeMCU TX
const uint8_t PIN_TX = 3;  // Arduino sends to NodeMCU RX

// ---------- NEMA17 Stepper motor pins ----------
const uint8_t PIN_STEP_OUT1 = 8;   // NEMA17 output 1
const uint8_t PIN_STEP_OUT2 = 9;   // NEMA17 output 2  
const uint8_t PIN_STEP_OUT3 = 10;  // NEMA17 output 3
const uint8_t PIN_STEP_OUT4 = 11;  // NEMA17 output 4
const uint8_t PIN_STEP_CONTROL = 12; // NEMA17 control pin

// ---------- IR Sensor pins ----------
const uint8_t PIN_IR_SENSOR1 = 4;  // IR sensor 1
const uint8_t PIN_IR_SENSOR2 = 5;  // IR sensor 2
const uint8_t PIN_IR_SENSOR3 = 6;  // IR sensor 3

// ---------- Other actuator pins ----------
const uint8_t PIN_DC_EN = 7;       // DC Motor Enable
const uint8_t PIN_SERVO1 = A0;     // Servo 1 (digital output on analog pin)
const uint8_t PIN_SERVO2 = A1;     // Servo 2 (digital output on analog pin)
const uint8_t PIN_PUMP = A2;       // Pump (digital output on analog pin)

// ---------- Servo positions ----------
const uint8_t SERVO_CLOSED = 60;   // closed position
const uint8_t SERVO_OPEN   = 120;  // open position

// ---------- State ----------
SoftwareSerial nodeSerial(PIN_RX, PIN_TX); // RX, TX for communication with NodeMCU
char serialBuffer[64]; // Fixed size buffer instead of String
uint8_t bufferIndex = 0;
bool lastIRSensor1State = false;
bool lastIRSensor2State = false;
bool lastIRSensor3State = false;
bool dcState = false;
bool pumpState = false;
bool stepperEnabled = false;   // Stepper motor enable state
uint8_t stepperDirection = 0; // 0 = left, 1 = right

// ---------- Servo state tracking ----------
bool servo1_state = false;  // Digital servo state
bool servo2_state = false;  // Digital servo state

// ---------- Smooth servo movement function (Updated) ----------
void setServoState(int servoId, bool state) {
  if (servoId == 1) {
    servo1_state = state;
    digitalWrite(PIN_SERVO1, state ? HIGH : LOW);
    Serial.print("[SERVO1] State: ");
    Serial.println(state ? 1 : 0);
    nodeSerial.print("[SERVO1] State: ");
    nodeSerial.println(state ? 1 : 0);
  } else if (servoId == 2) {
    servo2_state = state;
    digitalWrite(PIN_SERVO2, state ? HIGH : LOW);
    Serial.print("[SERVO2] State: ");
    Serial.println(state ? 1 : 0);
    nodeSerial.print("[SERVO2] State: ");
    nodeSerial.println(state ? 1 : 0);
  }
}

// ---------- Servo control functions (Digital output) ----------
void triggerServo1() {
  Serial.println("[SERVO1] Triggered");
  nodeSerial.println("[SERVO1] Triggered");
  setServoState(1, true);
  delay(500); // Pulse duration
  setServoState(1, false);
}

void triggerServo2() {
  Serial.println("[SERVO2] Triggered");
  nodeSerial.println("[SERVO2] Triggered");
  setServoState(2, true);
  delay(500); // Pulse duration
  setServoState(2, false);
}

// ---------- Actuator control functions ----------
void setupActuators() {
  // Setup NEMA17 stepper outputs and control
  pinMode(PIN_STEP_OUT1, OUTPUT);
  pinMode(PIN_STEP_OUT2, OUTPUT);
  pinMode(PIN_STEP_OUT3, OUTPUT);
  pinMode(PIN_STEP_OUT4, OUTPUT);
  pinMode(PIN_STEP_CONTROL, OUTPUT);
  
  // Setup IR sensors as inputs
  pinMode(PIN_IR_SENSOR1, INPUT_PULLUP);
  pinMode(PIN_IR_SENSOR2, INPUT_PULLUP);
  pinMode(PIN_IR_SENSOR3, INPUT_PULLUP);
  
  // Setup digital servo outputs
  pinMode(PIN_SERVO1, OUTPUT);
  pinMode(PIN_SERVO2, OUTPUT);
  
  pinMode(PIN_PUMP, OUTPUT);
  pinMode(PIN_DC_EN, OUTPUT);
  
  // Initialize to safe states
  digitalWrite(PIN_STEP_OUT1, LOW);
  digitalWrite(PIN_STEP_OUT2, LOW);
  digitalWrite(PIN_STEP_OUT3, LOW);
  digitalWrite(PIN_STEP_OUT4, LOW);
  digitalWrite(PIN_STEP_CONTROL, LOW);
  digitalWrite(PIN_SERVO1, LOW);
  digitalWrite(PIN_SERVO2, LOW);
  digitalWrite(PIN_PUMP, LOW);
  digitalWrite(PIN_DC_EN, LOW);
  
  // Initialize sensor states
  lastIRSensor1State = digitalRead(PIN_IR_SENSOR1);
  lastIRSensor2State = digitalRead(PIN_IR_SENSOR2);
  lastIRSensor3State = digitalRead(PIN_IR_SENSOR3);
  
  stepperDirection = 0; // Initialize to left (0)
  stepperEnabled = false; // Initialize stepper disabled
  servo1_state = false;
  servo2_state = false;
}

void setStepDirection(uint8_t direction) {
  stepperDirection = direction; // Store direction: 0=left, 1=right
  
  // Only set outputs if stepper is enabled
  if (stepperEnabled) {
    if (direction == 0) {
      // Turn left - set NEMA17 outputs for counter-clockwise
      Serial.println("[STEP] Direction: LEFT (0)");
      nodeSerial.println("[STEP] Direction: LEFT (0)");
      // Example pattern for left rotation:
      digitalWrite(PIN_STEP_OUT1, HIGH);
      digitalWrite(PIN_STEP_OUT2, LOW);
      digitalWrite(PIN_STEP_OUT3, LOW);
      digitalWrite(PIN_STEP_OUT4, LOW);
    } else {
      // Turn right - set NEMA17 outputs for clockwise  
      Serial.println("[STEP] Direction: RIGHT (1)");
      nodeSerial.println("[STEP] Direction: RIGHT (1)");
      // Example pattern for right rotation:
      digitalWrite(PIN_STEP_OUT1, LOW);
      digitalWrite(PIN_STEP_OUT2, HIGH);
      digitalWrite(PIN_STEP_OUT3, LOW);
      digitalWrite(PIN_STEP_OUT4, LOW);
    }
  } else {
    Serial.println("[STEP] Direction set but stepper disabled");
    nodeSerial.println("[STEP] Direction set but stepper disabled");
  }
}

void setStepperEnable(bool enable) {
  stepperEnabled = enable;
  digitalWrite(PIN_STEP_CONTROL, enable ? HIGH : LOW);
  Serial.print("[STEP] Stepper Enable: ");
  Serial.println(enable ? 1 : 0);
  nodeSerial.print("[STEP] Stepper Enable: ");
  nodeSerial.println(enable ? 1 : 0);
  
  // If enabling, apply current direction
  if (enable) {
    setStepDirection(stepperDirection);
  } else {
    // If disabling, turn off all coils
    digitalWrite(PIN_STEP_OUT1, LOW);
    digitalWrite(PIN_STEP_OUT2, LOW);
    digitalWrite(PIN_STEP_OUT3, LOW);
    digitalWrite(PIN_STEP_OUT4, LOW);
  }
}

void triggerServo1() {
  Serial.println("[SERVO1] Triggered");
  nodeSerial.println("[SERVO1] Triggered");
  setServoState(1, true);
  delay(500); // Pulse duration
  setServoState(1, false);
}

void triggerServo2() {
  Serial.println("[SERVO2] Triggered");
  nodeSerial.println("[SERVO2] Triggered");
  setServoState(2, true);
  delay(500); // Pulse duration
  setServoState(2, false);
}

void setPump(bool on) {
  pumpState = on;
  digitalWrite(PIN_PUMP, on ? HIGH : LOW);
  Serial.print("[PUMP] State set to ");
  Serial.println(on ? 1 : 0);
  nodeSerial.print("[PUMP] State set to ");
  nodeSerial.println(on ? 1 : 0);
}

void setDcState(bool on) {
  dcState = on;
  digitalWrite(PIN_DC_EN, on ? HIGH : LOW);
  Serial.print("[DC] Enable: ");
  Serial.println(on ? 1 : 0);
  nodeSerial.print("[DC] Enable: ");
  nodeSerial.println(on ? 1 : 0);
}

void controlServo(int servoId, int state) {
  switch (servoId) {
    case 1: 
      setServoState(1, state != 0);
      break;
    case 2: 
      setServoState(2, state != 0);
      break;
    default: 
      return;
  }
}

void processCommand(char* command) {
  Serial.print("[CMD] Received: ");
  Serial.println(command);
  
  // Parse STEP command: "STEP,0" (left) or "STEP,1" (right)
  if (strncmp(command, "STEP,", 5) == 0) {
    uint8_t direction = atoi(command + 5);
    setStepDirection(direction);
    Serial.println("done");
    nodeSerial.println("done");
    return;
  }
  
  // Parse STEP_EN command: "STEP_EN,0" (disable) or "STEP_EN,1" (enable)
  if (strncmp(command, "STEP_EN,", 8) == 0) {
    uint8_t enable = atoi(command + 8);
    setStepperEnable(enable != 0);
    Serial.println("done");
    nodeSerial.println("done");
    return;
  }
  
  // Legacy DIR command support: "DIR,L" or "DIR,R" 
  if (strncmp(command, "DIR,", 4) == 0) {
    char dirChar = command[4];
    uint8_t direction = (dirChar == 'L' || dirChar == 'l') ? 0 : 1;
    setStepDirection(direction);
    Serial.println("done");
    nodeSerial.println("done");
    return;
  }
  
  // Parse SERVO1 command: "SERVO1,1" or "SERVO1,0"
  if (strncmp(command, "SERVO1,", 7) == 0) {
    int value = atoi(command + 7);
    setServoState(1, value != 0);
    Serial.println("done");
    nodeSerial.println("done");
    return;
  }
  
  // Parse SERVO2 command: "SERVO2,1" or "SERVO2,0"
  if (strncmp(command, "SERVO2,", 7) == 0) {
    int value = atoi(command + 7);
    setServoState(2, value != 0);
    Serial.println("done");
    nodeSerial.println("done");
    return;
  }
  
  // Legacy SERVO5/SERVO6 support
  if (strncmp(command, "SERVO5,", 7) == 0) {
    triggerServo1(); // Map SERVO5 to SERVO1
    Serial.println("done");
    nodeSerial.println("done");
    return;
  }
  
  if (strncmp(command, "SERVO6,", 7) == 0) {
    triggerServo2(); // Map SERVO6 to SERVO2
    Serial.println("done");
    nodeSerial.println("done");
    return;
  }
  
  // Parse PUMP command: "PUMP,0" or "PUMP,1"
  if (strncmp(command, "PUMP,", 5) == 0) {
    int value = atoi(command + 5);
    setPump(value != 0);
    Serial.println("done");
    nodeSerial.println("done");
    return;
  }
  
  // Parse SERVO command: "SERVO,id,state"
  if (strncmp(command, "SERVO,", 6) == 0) {
    int servoId, state;
    if (sscanf(command + 6, "%d,%d", &servoId, &state) == 2) {
      controlServo(servoId, state);
      Serial.println("done");
      nodeSerial.println("done");
      return;
    }
  }
  
  // Parse DC command: "DC,0" or "DC,1"
  if (strncmp(command, "DC,", 3) == 0) {
    int value = atoi(command + 3);
    setDcState(value != 0);
    
    // Simulate processing sequence when DC starts
    if (value == 1) {
      Serial.println("[DC] Starting actuator sequence...");
      delay(2000); // Simulate processing time
      Serial.println("[DC] Sequence complete");
    }
    
    Serial.println("done");
    nodeSerial.println("done");
    return;
  }
  
  // Unknown command
  Serial.print("[ERROR] Unknown command: ");
  Serial.println(command);
}

void checkIRSensors() {
  // Check IR Sensor 1
  bool currentIR1 = digitalRead(PIN_IR_SENSOR1);
  if (currentIR1 && !lastIRSensor1State) {
    Serial.println("[IR1] Detected!");
    nodeSerial.println("ir1_detected");
    nodeSerial.println("1");
  }
  lastIRSensor1State = currentIR1;
  
  // Check IR Sensor 2
  bool currentIR2 = digitalRead(PIN_IR_SENSOR2);
  if (currentIR2 && !lastIRSensor2State) {
    Serial.println("[IR2] Detected!");
    nodeSerial.println("ir2_detected");
    nodeSerial.println("1");
  }
  lastIRSensor2State = currentIR2;
  
  // Check IR Sensor 3
  bool currentIR3 = digitalRead(PIN_IR_SENSOR3);
  if (currentIR3 && !lastIRSensor3State) {
    Serial.println("[IR3] Detected!");
    nodeSerial.println("ir3_detected");
    nodeSerial.println("1");
  }
  lastIRSensor3State = currentIR3;
}

// ---------- Setup / Loop ----------
void setup() {
  Serial.begin(9600);     // USB Serial for monitoring
  nodeSerial.begin(9600); // SoftwareSerial for NodeMCU communication
  delay(200);
  Serial.println(F("[ARDUINO2] Production controller ready"));
  Serial.println(F("[ARDUINO2] Using SoftwareSerial on pins 2(RX) and 3(TX)"));
  
  setupActuators();
  
  Serial.println(F("[ARDUINO2] Commands:"));
  Serial.println(F("  STEP,0/1 - Set stepper direction (0=left, 1=right)"));
  Serial.println(F("  STEP_EN,0/1 - Enable/disable stepper motor"));
  Serial.println(F("  SERVO1,0/1 - Control servo 1 (digital)"));
  Serial.println(F("  SERVO2,0/1 - Control servo 2 (digital)"));
  Serial.println(F("  PUMP,0/1 - Control pump"));
  Serial.println(F("  DC,0/1 - Enable/disable DC motor"));
  Serial.println(F("  NEMA17 outputs: pins 8,9,10,11, control pin 12"));
  Serial.println(F("  IR sensors: pins 4,5,6"));
  Serial.println(F("  DC enable: pin 7"));
  Serial.println(F("  Servos: A0,A1 (digital), Pump: A2"));
  
  // Clear buffer
  memset(serialBuffer, 0, sizeof(serialBuffer));
  bufferIndex = 0;
}

void loop() {
  // Read serial commands from NodeMCU via SoftwareSerial
  while (nodeSerial.available()) {
    char c = nodeSerial.read();
    if (c == '\n' || c == '\r') {
      if (bufferIndex > 0) {
        serialBuffer[bufferIndex] = '\0'; // null terminate
        processCommand(serialBuffer);
        bufferIndex = 0; // reset buffer
      }
    } else if (bufferIndex < sizeof(serialBuffer) - 1) {
      serialBuffer[bufferIndex++] = c;
    } else {
      // Buffer overflow protection - reset
      bufferIndex = 0;
    }
  }
  
  // Check IR sensor status
  checkIRSensors();
  
  delay(20); // Small delay for sensor debouncing
}