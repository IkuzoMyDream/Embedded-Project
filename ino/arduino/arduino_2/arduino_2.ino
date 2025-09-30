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
 * Serial Protocol:
 *   NodeMCU -> Arduino: "DIR,L/R" or "SERVO5,1" or "SERVO6,1" or "PUMP,1/0" or "DC,1/0"
 *   Arduino -> NodeMCU: "done" when operation complete
 */

#include <Arduino.h>
#include <SoftwareSerial.h>

// ---------- Communication pins ----------
const uint8_t PIN_RX = 2;  // Arduino receives from NodeMCU TX
const uint8_t PIN_TX = 3;  // Arduino sends to NodeMCU RX

// ---------- Actuator pins ----------
const uint8_t PIN_SERVO5 = 9;
const uint8_t PIN_SERVO6 = 10;
const uint8_t PIN_PUMP = 11;
const uint8_t PIN_DC_EN = 8;
const uint8_t PIN_DC_DIR = 7;
const uint8_t PIN_STEP_STEP = 5;
const uint8_t PIN_STEP_DIR = 6;

// ---------- Sensor pin ----------
const uint8_t PIN_SENSOR = 4;

// ---------- State ----------
SoftwareSerial nodeSerial(PIN_RX, PIN_TX); // RX, TX for communication with NodeMCU
String serialBuffer = "";
bool lastSensorState = false;
bool dcState = false;
bool pumpState = false;

// ---------- Actuator control functions ----------
void setupActuators() {
  pinMode(PIN_SERVO5, OUTPUT);
  pinMode(PIN_SERVO6, OUTPUT);
  pinMode(PIN_PUMP, OUTPUT);
  pinMode(PIN_DC_EN, OUTPUT);
  pinMode(PIN_DC_DIR, OUTPUT);
  pinMode(PIN_STEP_STEP, OUTPUT);
  pinMode(PIN_STEP_DIR, OUTPUT);
  pinMode(PIN_SENSOR, INPUT_PULLUP);
  
  // Initialize to safe states
  digitalWrite(PIN_SERVO5, LOW);
  digitalWrite(PIN_SERVO6, LOW);
  digitalWrite(PIN_PUMP, LOW);
  digitalWrite(PIN_DC_EN, LOW);
  digitalWrite(PIN_DC_DIR, LOW);
  digitalWrite(PIN_STEP_STEP, LOW);
  digitalWrite(PIN_STEP_DIR, LOW);
  
  lastSensorState = digitalRead(PIN_SENSOR);
}

void setStepDirection(char direction) {
  if (direction == 'L' || direction == 'l') {
    digitalWrite(PIN_STEP_DIR, LOW);  // Left/Counter-clockwise
    Serial.println("[STEP] Direction: LEFT");
    nodeSerial.println("[STEP] Direction: LEFT");
  } else {
    digitalWrite(PIN_STEP_DIR, HIGH); // Right/Clockwise
    Serial.println("[STEP] Direction: RIGHT");
    nodeSerial.println("[STEP] Direction: RIGHT");
  }
}

void triggerServo5() {
  Serial.println("[SERVO5] Triggered");
  nodeSerial.println("[SERVO5] Triggered");
  digitalWrite(PIN_SERVO5, HIGH);
  delay(500); // Pulse duration
  digitalWrite(PIN_SERVO5, LOW);
}

void triggerServo6() {
  Serial.println("[SERVO6] Triggered");
  nodeSerial.println("[SERVO6] Triggered");
  digitalWrite(PIN_SERVO6, HIGH);
  delay(500); // Pulse duration
  digitalWrite(PIN_SERVO6, LOW);
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
  Serial.print("[DC] State set to ");
  Serial.println(on ? 1 : 0);
  nodeSerial.print("[DC] State set to ");
  nodeSerial.println(on ? 1 : 0);
}

void processCommand(String command) {
  command.trim();
  if (command.length() == 0) return;
  
  Serial.print("[CMD] Received: ");
  Serial.println(command);
  
  // Parse DIR command: "DIR,L" or "DIR,R"
  if (command.startsWith("DIR,")) {
    char direction = command.charAt(4);
    setStepDirection(direction);
    Serial.println("done");
    nodeSerial.println("done");
    return;
  }
  
  // Parse SERVO5 command: "SERVO5,1"
  if (command.startsWith("SERVO5,")) {
    triggerServo5();
    Serial.println("done");
    nodeSerial.println("done");
    return;
  }
  
  // Parse SERVO6 command: "SERVO6,1"
  if (command.startsWith("SERVO6,")) {
    triggerServo6();
    Serial.println("done");
    nodeSerial.println("done");
    return;
  }
  
  // Parse PUMP command: "PUMP,0" or "PUMP,1"
  if (command.startsWith("PUMP,")) {
    int value = command.substring(5).toInt();
    setPump(value != 0);
    Serial.println("done");
    nodeSerial.println("done");
    return;
  }
  
  // Parse DC command: "DC,0" or "DC,1"
  if (command.startsWith("DC,")) {
    int value = command.substring(3).toInt();
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

void checkSensor() {
  bool currentState = digitalRead(PIN_SENSOR);
  if (currentState && !lastSensorState) {
    // Sensor triggered (rising edge)
    Serial.println("[SENSOR] Detected!");
    nodeSerial.println("sensor_done");
    nodeSerial.println("1"); // Sensor value
  }
  lastSensorState = currentState;
}

// ---------- Setup / Loop ----------
void setup() {
  Serial.begin(9600);     // USB Serial for monitoring
  nodeSerial.begin(9600); // SoftwareSerial for NodeMCU communication
  delay(200);
  Serial.println("[ARDUINO2] Production controller ready");
  Serial.println("[ARDUINO2] Using SoftwareSerial on pins 2(RX) and 3(TX)");
  
  setupActuators();
  
  Serial.println("[ARDUINO2] Commands:");
  Serial.println("  DIR,L/R - Set stepper direction");
  Serial.println("  SERVO5,1 - Trigger servo 5");
  Serial.println("  SERVO6,1 - Trigger servo 6");
  Serial.println("  PUMP,0/1 - Control pump");
  Serial.println("  DC,0/1 - Control DC motor");
}

void loop() {
  // Read serial commands from NodeMCU via SoftwareSerial
  while (nodeSerial.available()) {
    char c = nodeSerial.read();
    if (c == '\n' || c == '\r') {
      if (serialBuffer.length() > 0) {
        processCommand(serialBuffer);
        serialBuffer = "";
      }
    } else {
      serialBuffer += c;
      // Prevent buffer overflow
      if (serialBuffer.length() > 200) {
        serialBuffer = serialBuffer.substring(serialBuffer.length() - 200);
      }
    }
  }
  
  // Check sensor status
  checkSensor();
  
  delay(20); // Small delay for sensor debouncing
}