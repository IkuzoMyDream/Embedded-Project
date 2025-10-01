/* arduino_2.ino — Simplified Arduino controller for NodeMCU2
 * Role: Receive commands via SoftwareSerial from NodeMCU and control stepper/servos/pump/DC
 * Communication: NodeMCU sends CSV commands, Arduino responds with "ack" and "done"
 *
 * Hardware connections:
 *   NodeMCU TX (D6/GPIO12) -> Arduino Pin 2 (RX)
 *   NodeMCU RX (D7/GPIO13) -> Arduino Pin 3 (TX)
 *   GND -> GND
 *
 * Pin Assignments:
 *   Pins 8,9,10,13 -> NEMA17 Stepper Motor Outputs
 *   Pins 2,3 -> TX/RX Communication
 *   Pins 4,5,6 -> IR Sensors 1,2,3
 *   Pin 7 -> DC Motor Enable
 *   Pin 12 -> Pump
 *   Pin 11 -> Servo 1 (Digital output) 
 *
 * Simplified Control:
 *   - Receive STEP command -> Start operation with 30s timeout
 *   - Set target room -> Monitor IR sensor for that room
 *   - IR detection -> Stop operation and send "done"
 *   - Simple state management with minimal dependencies
 */

#include <Arduino.h>
#include <SoftwareSerial.h>
#include <Stepper.h>
#include <Servo.h>

// Servo myServo;
// ---------- Communication pins ----------
const uint8_t PIN_RX = 2;  // Arduino receives from NodeMCU TX
const uint8_t PIN_TX = 3;  // Arduino sends to NodeMCU RX

// ---------- NEMA17 Stepper motor configuration ----------
const int stepsPerRevolution = 200;  // Steps per revolution for NEMA17
Stepper myStepper(stepsPerRevolution, 8, 9, 10, 13);  // Initialize stepper on pins 8,9,10,13

// ---------- IR Sensor pins ----------
const uint8_t PIN_IR_SENSOR1 = 4;  // IR sensor 1
const uint8_t PIN_IR_SENSOR2 = 5;  // IR sensor 2
const uint8_t PIN_IR_SENSOR3 = 6;  // IR sensor 3

// ---------- Other actuator pins ----------
const uint8_t PIN_DC_EN = 7;       // DC Motor Enable
const uint8_t PIN_PUMP = 12;       // Pump 
// const uint8_t PIN_SERVO1 = 11;     // Servo 1 (digital output)

// ---------- Communication ----------
SoftwareSerial nodeSerial(PIN_RX, PIN_TX); // RX, TX for communication with NodeMCU
char serialBuffer[64]; // Fixed size buffer
uint8_t bufferIndex = 0;

// ---------- Simplified State ----------
bool isOperating = false;       // Is system currently operating?
int targetRoom = -1;            // Which room we're targeting (1,2,3)
int stepDirection = 0;          // 0 = clockwise, 1 = counterclockwise
unsigned long operationStartTime = 0;
const unsigned long OPERATION_TIMEOUT = 30000; // 30 seconds timeout

// IR Sensor edge detection
bool lastIRSensor1State = false;
bool lastIRSensor2State = false;
bool lastIRSensor3State = false;

// Stepper control
unsigned long lastStepTime = 0;
const unsigned long stepInterval = 100; // Step every 100ms

// Pump auto-stop timer
unsigned long pumpStartTime = 0;
const unsigned long PUMP_RUN_DURATION = 1000; // 1 second
bool pumpAutoStop = false;

// ---------- Simple actuator functions ----------
// void triggerServo() {
//   digitalWrite(PIN_SERVO1, HIGH);
//   delay(500); // Pulse duration
//   digitalWrite(PIN_SERVO1, LOW);
//   Serial.println("[SERVO] Triggered");
// }

// void triggerServoDirection(int room) {
//   if (room == 2) {
//     // Room 2 -> หัน left
//     myServo.write(1);    // มุมตรงกลาง

//     Serial.println("[SERVO] Room 2 - Turn LEFT");
//   } else if (room == 3) {
//     // Room 3 -> หัน right  
//     myServo.write(45);    // มุมตรงกลาง

//     Serial.println("[SERVO] Room 3 - Turn RIGHT");
//   } else {
//     // Default trigger
//     triggerServo();
//   }
// }
 
void setPump(bool on) {
  digitalWrite(PIN_PUMP, on ? HIGH : LOW);
  Serial.print("[PUMP] ");
  Serial.println(on ? "ON" : "OFF");
  
  if (on) {
    // Start pump timer for auto-stop after 1 second
    pumpStartTime = millis();
    pumpAutoStop = true;
  } else {
    // Manual stop - clear timer
    pumpAutoStop = false;
  }
}

void setDC(bool on) {
  digitalWrite(PIN_DC_EN, on ? HIGH : LOW);
  Serial.print("[DC] ");
  Serial.println(on ? "ON" : "OFF");
}

// ---------- Hardware setup ----------
void setupHardware() {
  // Configure stepper motor speed
  myStepper.setSpeed(10); // RPM
  
  // Set pin modes
  pinMode(PIN_IR_SENSOR1, INPUT);
  pinMode(PIN_IR_SENSOR2, INPUT);
  pinMode(PIN_IR_SENSOR3, INPUT);
  pinMode(PIN_DC_EN, OUTPUT);
  pinMode(PIN_PUMP, OUTPUT);
  // pinMode(PIN_SERVO1, OUTPUT); // Commented out - no servo
  
  // Initialize outputs to OFF
  digitalWrite(PIN_DC_EN, LOW);
  digitalWrite(PIN_PUMP, LOW);
  // digitalWrite(PIN_SERVO1, LOW); // Commented out - no servo
  
  Serial.println("[HARDWARE] Setup complete");
}

// ---------- Emergency stop all motors ----------
void emergencyStopAll() {
  // Force stop everything immediately
  digitalWrite(PIN_DC_EN, LOW);    // DC motor OFF
  digitalWrite(PIN_PUMP, LOW);     // Pump OFF
  // digitalWrite(PIN_SERVO1, LOW); // Servo OFF - commented out
  
  // Reset operation state
  isOperating = false;
  targetRoom = -1;
  stepDirection = 0;
  pumpAutoStop = false; // Clear pump timer
  
  Serial.println("[EMERGENCY] All systems stopped!");
}

// ---------- Operation control ----------
void startOperation(int room, int direction) {
  isOperating = true;
  targetRoom = room;
  stepDirection = direction;
  operationStartTime = millis();
  
  Serial.print("[OP] Started - Room:");
  Serial.print(room);
  Serial.print(" Dir:");
  Serial.println(direction);
}

void stopOperation(const char* reason) {
  if (!isOperating) return;
  
  isOperating = false;
  Serial.print("[OP] Stopped - ");
  Serial.println(reason);
  
  // Stop ALL motors and actuators immediately
  setDC(false);          // Stop DC motor
  setPump(false);        // Stop pump (this will clear auto timer)
  // digitalWrite(PIN_SERVO1, LOW);  // Stop servo - commented out
  
  // Note: Stepper motor will stop automatically in stepperLoop() 
  // when isOperating = false
  
  Serial.println("[SYSTEM] All motors and actuators stopped");
  
  // Send done to NodeMCU
  nodeSerial.println("done");
  
  // Reset simple state
  targetRoom = -1;
  stepDirection = 0;
}

// ---------- Stepper loop with timeout ----------
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

// ---------- Pump auto-stop check ----------
void checkPumpTimer() {
  if (pumpAutoStop && (millis() - pumpStartTime > PUMP_RUN_DURATION)) {
    // Auto stop pump after 1 second
    digitalWrite(PIN_PUMP, LOW);
    pumpAutoStop = false;
    Serial.println("[PUMP] Auto-stopped after 1 second");
  }
}

// ---------- IR sensor monitoring ----------
void checkIRSensors() {
  if (!isOperating || targetRoom < 1 || targetRoom > 3) return;
  
  bool detected = false;
  
  // Check the target room's IR sensor (Detect when box LEAVES: LOW -> HIGH)
  if (targetRoom == 1) {
    bool current = digitalRead(PIN_IR_SENSOR1);
    detected = current && !lastIRSensor1State;  // Detect LOW -> HIGH (box removed)
    
    // Debug output
    Serial.print("[IR1] Current:");
    Serial.print(current);
    Serial.print(" Last:");
    Serial.print(lastIRSensor1State);
    Serial.print(" Detected:");
    Serial.println(detected);
    
    lastIRSensor1State = current;
  } else if (targetRoom == 2) {
    bool current = digitalRead(PIN_IR_SENSOR2);
    detected = current && !lastIRSensor2State;  // Detect LOW -> HIGH (box removed)
    
    // Debug output
    Serial.print("[IR2] Current:");
    Serial.print(current);
    Serial.print(" Last:");
    Serial.print(lastIRSensor2State);
    Serial.print(" Detected:");
    Serial.println(detected);
    
    lastIRSensor2State = current;
  } else if (targetRoom == 3) {
    bool current = digitalRead(PIN_IR_SENSOR3);
    detected = current && !lastIRSensor3State;  // Detect LOW -> HIGH (box removed)
    
    // Debug output
    Serial.print("[IR3] Current:");
    Serial.print(current);
    Serial.print(" Last:");
    Serial.print(lastIRSensor3State);
    Serial.print(" Detected:");
    Serial.println(detected);
    
    lastIRSensor3State = current;
  }
  
  if (detected) {
    Serial.print("[IR");
    Serial.print(targetRoom);
    Serial.println("] DETECTED - Box removed from sensor!");
    stopOperation("IR_DETECTED");
  }
}

// ---------- Command processing ----------
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
  
  // Simple servo trigger with direction based on room
  // if (strncmp(command, "SERVO1,1", 8) == 0 || strncmp(command, "SERVO5,1", 8) == 0) {
    // triggerServoDirection(targetRoom); // Use current target room for direction
  //   Serial.println("ack");
  //   nodeSerial.println("ack");
  //   return;
  // }
  
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
  
  // Emergency stop all
  if (strncmp(command, "EMERGENCY", 9) == 0) {
    emergencyStopAll();
    Serial.println("ack");
    nodeSerial.println("ack");
    return;
  }
  
  // Unknown command
  Serial.print("[ERROR] Unknown command: ");
  Serial.println(command);
}

// ---------- Setup / Loop ----------
void setup() {
  Serial.begin(9600);     
  nodeSerial.begin(9600);
  // myServo.attach(PIN_SERVO1); // Commented out - no servo  
  delay(200);
  Serial.println(F("[ARDUINO2] Simplified controller ready"));
  Serial.println(F("[ARDUINO2] Commands: STEP,0/1 ROOM,1/2/3 PUMP,0/1 DC,0/1 STOP"));
   
  setupHardware();
  
  // Initialize IR sensor states with actual readings
  lastIRSensor1State = digitalRead(PIN_IR_SENSOR1);
  lastIRSensor2State = digitalRead(PIN_IR_SENSOR2);
  lastIRSensor3State = digitalRead(PIN_IR_SENSOR3);
  
  Serial.print("[IR] Initial states - IR1:");
  Serial.print(lastIRSensor1State);
  Serial.print(" IR2:");
  Serial.print(lastIRSensor2State);
  Serial.print(" IR3:");
  Serial.println(lastIRSensor3State);
  
  // Clear buffer
  memset(serialBuffer, 0, sizeof(serialBuffer));
  bufferIndex = 0;
  
  // Initialize simple state
  isOperating = false;
  targetRoom = 0;
  stepDirection = 0;
  pumpAutoStop = false; // Initialize pump timer
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
  
  // Simple operation loop
  stepperLoop();
  checkIRSensors();
  checkPumpTimer(); // Check pump auto-stop timer
  
  delay(1);
}