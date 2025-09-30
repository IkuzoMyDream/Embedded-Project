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
 *   Pins 2,3 -> TX/RX Communication
 *   Pins 4,5,6 -> IR Sensors 1,2,3
 *   Pin 7 -> DC Motor Enable
 *   Pin 12 -> Pump
 *   Pin A0 -> Servo 1 (Digital output) 
 *
 * Serial Protocol:
 *   NodeMCU -> Arduino: "ROOM,1/2/3" or "STEP,0/1" or "SERVO1,0/1" or "SERVO5,1" or "PUMP,0/1" or "DC,0/1"
 *   Arduino -> NodeMCU: "ack" for command acknowledgment, "done" when IR detection complete
 *   
 *   Control Scheme:
 *     ROOM,1/2/3 = Set target room for IR detection
 *     STEP,0 = Turn Clockwise (0)
 *     STEP,1 = Turn Counterclockwise (1)
 *     SERVO1,0/1 = Digital servo control
 *     SERVO5,1 = Legacy mapping to SERVO1
 *     DC,0/1 = Disable/Enable DC Motor (stops stepper when enabled)
 *     PUMP,0/1 = Disable/Enable Pump
 *     IR sensors report detection automatically for active target room
 */

#include <Arduino.h>
#include <SoftwareSerial.h>
#include <Stepper.h>

// ---------- Communication pins ----------
const uint8_t PIN_RX = 2;  // Arduino receives from NodeMCU TX
const uint8_t PIN_TX = 3;  // Arduino sends to NodeMCU RX

// ---------- NEMA17 Stepper motor configuration ----------
const int stepsPerRevolution = 200;  // Steps per revolution for NEMA17
Stepper myStepper(stepsPerRevolution, 8, 9, 10, 11);  // Initialize stepper on pins 8-11

// ---------- IR Sensor pins ----------
const uint8_t PIN_IR_SENSOR1 = 4;  // IR sensor 1
const uint8_t PIN_IR_SENSOR2 = 5;  // IR sensor 2
const uint8_t PIN_IR_SENSOR3 = 6;  // IR sensor 3

// ---------- Other actuator pins ----------
const uint8_t PIN_DC_EN = 7;       // DC Motor Enable
const uint8_t PIN_PUMP = 12;       // Pump 
const uint8_t PIN_SERVO1 = A0;     // Servo 1 (digital output on analog pin)

// ---------- Servo positions ----------
const uint8_t SERVO_CLOSED = 60;   // closed position
const uint8_t SERVO_OPEN   = 120;  // open position

// ---------- State (Simplified) ----------
SoftwareSerial nodeSerial(PIN_RX, PIN_TX); // RX, TX for communication with NodeMCU
char serialBuffer[64]; // Fixed size buffer instead of String
uint8_t bufferIndex = 0;

// IR Sensor states
bool lastIRSensor1State = false;
bool lastIRSensor2State = false;
bool lastIRSensor3State = false;

// Simple operation state
bool isOperating = false;       // Is system currently operating?
int targetRoom = -1;            // Which room we're targeting (1,2,3)
int stepDirection = 0;          // 0 = clockwise, 1 = counterclockwise
unsigned long operationStartTime = 0;
const unsigned long OPERATION_TIMEOUT = 30000; // 30 seconds timeout

// Stepper control
unsigned long lastStepTime = 0;
const unsigned long stepInterval = 100; // Step every 100ms

// ---------- Simple actuator functions ----------
void triggerServo() {
  digitalWrite(PIN_SERVO1, HIGH);
  delay(500); // Pulse duration
  digitalWrite(PIN_SERVO1, LOW);
  Serial.println("[SERVO] Triggered");
}

void setPump(bool on) {
  digitalWrite(PIN_PUMP, on ? HIGH : LOW);
  Serial.print("[PUMP] ");
  Serial.println(on ? "ON" : "OFF");
}

void setDC(bool on) {
  digitalWrite(PIN_DC_EN, on ? HIGH : LOW);
  Serial.print("[DC] ");
  Serial.println(on ? "ON" : "OFF");
}

void setupHardware() {
  // Setup stepper speed
  myStepper.setSpeed(60);  // 60 RPM
  
  // Setup pins
  pinMode(PIN_IR_SENSOR1, INPUT_PULLUP);
  pinMode(PIN_IR_SENSOR2, INPUT_PULLUP);
  pinMode(PIN_IR_SENSOR3, INPUT_PULLUP);
  pinMode(PIN_SERVO1, OUTPUT);
  pinMode(PIN_PUMP, OUTPUT);
  pinMode(PIN_DC_EN, OUTPUT);
  
  // Initialize to OFF
  digitalWrite(PIN_SERVO1, LOW);
  digitalWrite(PIN_PUMP, LOW);
  digitalWrite(PIN_DC_EN, LOW);
  
  // Read initial IR states
  lastIRSensor1State = digitalRead(PIN_IR_SENSOR1);
  lastIRSensor2State = digitalRead(PIN_IR_SENSOR2);
  lastIRSensor3State = digitalRead(PIN_IR_SENSOR3);
  
  Serial.println("[SETUP] Hardware initialized");
}

// ---------- Main operation control ----------
void startOperation(int room, int direction) {
  targetRoom = room;
  stepDirection = direction;
  isOperating = true;
  operationStartTime = millis();
  
  Serial.print("[OP] Started - Room:");
  Serial.print(room);
  Serial.print(" Dir:");
  Serial.println(direction == 0 ? "CW" : "CCW");
}

void stopOperation(const char* reason) {
  isOperating = false;
  targetRoom = -1;
  
  // Stop all actuators
  setDC(false);
  setPump(false);
  
  Serial.print("[OP] Stopped - ");
  Serial.println(reason);
  nodeSerial.println("done");
}

void stepperLoop() {
  if (!isOperating) return;
  
  // Check timeout
  if (millis() - operationStartTime > OPERATION_TIMEOUT) {
    stopOperation("TIMEOUT");
    return;
  }
  
  // Step motor
  if (millis() - lastStepTime > stepInterval) {
    lastStepTime = millis();
    
    if (stepDirection == 0) {
      myStepper.step(10);  // Clockwise
    } else {
      myStepper.step(-10); // Counterclockwise
    }
  }
}

// ---------- Queue management functions ----------
void setTargetRoom(int room) {
  activeTargetRoom = room;
  waitingForIRDetection = true;
  Serial.print("[QUEUE] Waiting for IR sensor ");
  Serial.print(room);
  Serial.println(" to detect");
  nodeSerial.print("[QUEUE] Waiting for IR sensor ");
  nodeSerial.print(room);
  nodeSerial.println(" to detect");
}

void sendQueueDone() {
  Serial.print("[QUEUE] Room ");
  Serial.print(activeTargetRoom);
  Serial.println(" completed - sending done");
  
  // Pause stepper but keep state (don't clear stepperRunning or stepperDirection)
  stepperPaused = true;          // Pause stepper movement but keep state
  setDcState(false);            // Stop DC motor
  setPump(false);               // Stop pump
  setServoState(1, false);      // Stop servo
  
  Serial.println("[SYSTEM] Stepper paused (state preserved), other actuators stopped");
  nodeSerial.println("[SYSTEM] Stepper paused (state preserved), other actuators stopped");
  
  nodeSerial.println("done");   // Send done to NodeMCU
  
  // Reset queue state
  activeTargetRoom = -1;
  waitingForIRDetection = false;
  
  Serial.print("[SYSTEM] Queue cleared - Stepper state: running=");
  Serial.print(stepperRunning ? "true" : "false");
  Serial.print(", paused=");
  Serial.print(stepperPaused ? "true" : "false");
  Serial.print(", direction=");
  Serial.println(stepperDirection);
}

// ---------- System state management ----------
void clearAllStates() {
  // Stop all motors and actuators
  stepperRunning = false;
  stepperPaused = false;        // Clear paused state
  setDcState(false);
  setPump(false); 
  setServoState(1, false);
  
  // Reset state variables
  dcState = false;
  pumpState = false;
  servo1_state = false;
  stepperDirection = 0;
  
  // Reset queue tracking
  activeTargetRoom = -1;
  waitingForIRDetection = false;
  
  Serial.println("[SYSTEM] Complete state reset performed - all states cleared");
}

// ---------- Stepper resume function ----------
void resumeStepper() {
  if (stepperRunning && stepperPaused) {
    stepperPaused = false;
    Serial.print("[STEPPER] Resumed - direction=");
    Serial.println(stepperDirection);
    nodeSerial.print("[STEPPER] Resumed - direction=");
    nodeSerial.println(stepperDirection);
  } else {
    Serial.println("[STEPPER] Cannot resume - not in paused state");
  }
}

// ---------- Individual IR sensor check functions ----------
bool checkIRSensor1() {
  bool currentIR1 = digitalRead(PIN_IR_SENSOR1);
  bool detected = currentIR1 && !lastIRSensor1State;
  lastIRSensor1State = currentIR1;
  return detected;
}

bool checkIRSensor2() {
  bool currentIR2 = digitalRead(PIN_IR_SENSOR2);
  bool detected = currentIR2 && !lastIRSensor2State;
  lastIRSensor2State = currentIR2;
  return detected;
}

bool checkIRSensor3() {
  bool currentIR3 = digitalRead(PIN_IR_SENSOR3);
  bool detected = currentIR3 && !lastIRSensor3State;
  lastIRSensor3State = currentIR3;
  return detected;
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
  
  // Parse STEP command: "STEP,0" (clockwise) or "STEP,1" (counterclockwise)
  if (strncmp(command, "STEP,", 5) == 0) {
    int direction = atoi(command + 5);
    // Simple operation start - no complex state
    isOperating = true;
    stepDirection = (direction == 0) ? 0 : 1;
    operationStartTime = millis();
    
    Serial.print("[STEP] Started direction ");
    Serial.println(stepDirection);
    Serial.println("ack");
    nodeSerial.println("ack");
    return;
  }
  
  // Parse ROOM command: "ROOM,1/2/3" - Set target room for IR detection
  if (strncmp(command, "ROOM,", 5) == 0) {
    int room = atoi(command + 5);
    if (room >= 1 && room <= 3) {
      targetRoom = room;
      Serial.print("[ROOM] Target set to ");
      Serial.println(room);
      Serial.println("ack");
      nodeSerial.println("ack");
    } else {
      Serial.println("error");
      nodeSerial.println("error");
    }
    return;
  }
  
  // Simple servo trigger
  if (strncmp(command, "SERVO1,1", 8) == 0 || strncmp(command, "SERVO5,1", 8) == 0) {
    triggerServo();
    Serial.println("ack");
    nodeSerial.println("ack");
    return;
  }
  
  // Simple pump control
  if (strncmp(command, "PUMP,", 5) == 0) {
    int value = atoi(command + 5);
    setPump(value != 0);
    Serial.println("ack");
    nodeSerial.println("ack");
    return;
  }
  
  // Simple DC control
  if (strncmp(command, "DC,", 3) == 0) {
    int value = atoi(command + 3);
    setDC(value != 0);
    Serial.println("ack");
    nodeSerial.println("ack");
    return;
  }
  
  // Stop operation
  if (strncmp(command, "STOP", 4) == 0 || strncmp(command, "RESET", 5) == 0) {
    stopOperation("MANUAL_STOP");
    Serial.println("ack");
    nodeSerial.println("ack");
    return;
  }
  
  // Unknown command
  Serial.print("[ERROR] Unknown command: ");
  Serial.println(command);
}

// ---------- IR sensor monitoring ----------
void checkIRSensors() {
  if (!isOperating || targetRoom < 1 || targetRoom > 3) return;
  
  bool detected = false;
  
  // Check the target room's IR sensor
  if (targetRoom == 1) {
    bool current = digitalRead(PIN_IR_SENSOR1);
    detected = current && !lastIRSensor1State;
    lastIRSensor1State = current;
  } else if (targetRoom == 2) {
    bool current = digitalRead(PIN_IR_SENSOR2);
    detected = current && !lastIRSensor2State;
    lastIRSensor2State = current;
  } else if (targetRoom == 3) {
    bool current = digitalRead(PIN_IR_SENSOR3);
    detected = current && !lastIRSensor3State;
    lastIRSensor3State = current;
  }
  
  if (detected) {
    Serial.print("[IR");
    Serial.print(targetRoom);
    Serial.println("] DETECTED");
    stopOperation("IR_DETECTED");
  }
}

// ---------- Setup / Loop ----------
void setup() {
  Serial.begin(9600);     
  nodeSerial.begin(9600); 
  delay(200);
  Serial.println(F("[ARDUINO2] Simplified controller ready"));
  Serial.println(F("[ARDUINO2] Commands: STEP,0/1 ROOM,1/2/3 SERVO1,1 PUMP,0/1 DC,0/1 STOP"));
   
  setupHardware();
  
  // Clear buffer
  memset(serialBuffer, 0, sizeof(serialBuffer));
  bufferIndex = 0;
  
  // Initialize simple state
  isOperating = false;
  targetRoom = 0;
  stepDirection = 0;
}

void loop() {
  // Read serial commands from NodeMCU via SoftwareSerial
  while (nodeSerial.available()) {
    char c = nodeSerial.read();
    if (c == '\n' || c == '\r') {
      if (bufferIndex > 0) {
        serialBuffer[bufferIndex] = '\0';
        processCommand(serialBuffer);
        bufferIndex = 0;
      }
    } else if (bufferIndex < sizeof(serialBuffer) - 1) {
      serialBuffer[bufferIndex++] = c;
    } else {
      bufferIndex = 0; // Buffer overflow protection
    }
  }
  
  // Simple operation loop
  stepperLoop();
  checkIRSensors();
  
  delay(1);
}