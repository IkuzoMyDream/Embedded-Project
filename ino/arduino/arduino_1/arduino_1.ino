/* arduino_1.ino — Arduino controller for NodeMCU1 (SoftwareSerial communication)
 * Role: Receive commands via SoftwareSerial from NodeMCU and control servos/actuators
 * Communication: NodeMCU sends CSV commands, Arduino responds with "done"
 *
 * Hardware connections:
 *   NodeMCU TX (D6/GPIO12) -> Arduino Pin 2 (RX)
 *   NodeMCU RX (D7/GPIO13) -> Arduino Pin 3 (TX)
 *   GND -> GND
 *   Both devices can be connected to USB separately for programming/monitoring
 *
 * Arduino OUTPUTS to actuators (you can wire to drivers/servos):
 *   Servo1 out -> Pin 9  (pill_id = 1)
 *   Servo2 out -> Pin 10 (pill_id = 2)
 *   Servo3 out -> Pin 11 (pill_id = 3)
 *   Servo4 out -> Pin 12 (pill_id = 4)
 *   DC_EN out  -> Pin 8  (ON/OFF only)
 *
 * Pill ID Mapping:
 *   pill_id 1 -> Servo 1 (Pin 9)
 *   pill_id 2 -> Servo 2 (Pin 10)
 *   pill_id 3 -> Servo 3 (Pin 11)
 *   pill_id 4 -> Servo 4 (Pin 12)
 *
 * Serial Protocol:
 *   NodeMCU -> Arduino: "queue_id,pill_id,quantity" or "DC,0/1" or "SERVO,id,pos"
 *   Arduino -> NodeMCU: "done" when operation complete
 */

#include <Arduino.h>
#include <Servo.h>
#include <SoftwareSerial.h>

// ---------- Communication pins ----------
const uint8_t PIN_RX = 2;  // Arduino receives from NodeMCU TX
const uint8_t PIN_TX = 3;  // Arduino sends to NodeMCU RX

// ---------- Servo outputs ---------- 
const uint8_t PIN_SERVO1_OUT = 9;
const uint8_t PIN_SERVO2_OUT = 10;
const uint8_t PIN_SERVO3_OUT = 11;
const uint8_t PIN_SERVO4_OUT = 12;

// ---------- DC motor outputs ----------
const uint8_t PIN_DC_EN_OUT  = 8;  // ON/OFF enable line

// ---------- Servo positions ----------
const uint8_t SERVO_CLOSED = 60;   // closed position
const uint8_t SERVO_OPEN   = 120;  // open position

// ---------- DC auto-stop timing ----------
const unsigned long DC_AUTO_STOP_MS = 15000; // 15 seconds auto-stop

// ---------- State ----------
Servo servo1, servo2, servo3, servo4;
SoftwareSerial nodeSerial(PIN_RX, PIN_TX); // RX, TX for communication with NodeMCU
char serialBuffer[64]; // Fixed size buffer instead of String
uint8_t bufferIndex = 0;

// ---------- DC motor timing state ----------
bool dc_running = false;
unsigned long dc_start_time = 0;

// ---------- Servo state tracking ----------
bool servo1_isLeft = false;  // false=ขวา(60°), true=ซ้าย(120°)
bool servo2_isLeft = false;
bool servo3_isLeft = false;
bool servo4_isLeft = false;

// ---------- Smooth servo movement function (Updated) ----------
void smoothMove(Servo &servo, int startPos, int endPos) {
  if (startPos < endPos) {
    for (int pos = startPos; pos <= endPos; pos++) {
      servo.write(pos);
      delay(2);  // smooth movement
    }
  } else {
    for (int pos = startPos; pos >= endPos; pos--) {
      servo.write(pos);
      delay(2);
    }
  }
}

// ---------- Servo logic control functions (IMPLEMENTED) ----------
// Each servo has different toggle patterns for different pill types

void servoLogic1(int pulses = 1) {
  // Servo 1 - alternating right(60°)/left(120°) movement with state memory
  for (int p = 0; p < pulses; p++) {
    int currentPos = servo1.read();
    
    // Toggle state: ขวา(60°) <-> ซ้าย(120°)
    servo1_isLeft = !servo1_isLeft;
    int targetPos = servo1_isLeft ? 120 : 60;  // true=ซ้าย(120°), false=ขวา(60°)
    
    smoothMove(servo1, currentPos, targetPos);
    delay(200); // หน่วงเวลาเปิด (reduced from 500ms)
    
    if (p < pulses - 1) {
      delay(50); // pause between movements (reduced from 100ms)
    }
  }
}

void servoLogic2(int pulses = 1) {
  // Servo 2 - alternating right(60°)/left(120°) movement with state memory
  for (int p = 0; p < pulses; p++) {
    int currentPos = servo2.read();
    
    // Toggle state: ขวา(60°) <-> ซ้าย(120°)
    servo2_isLeft = !servo2_isLeft;
    int targetPos = servo2_isLeft ? 120 : 60;
    
    smoothMove(servo2, currentPos, targetPos);
    delay(250); // หน่วงเวลาเปิด (reduced from 700ms)
    
    if (p < pulses - 1) {
      delay(50); // pause between movements (reduced from 100ms)
    }
  }
}

void servoLogic3(int pulses = 1) {
  // Servo 3 - alternating right(60°)/left(120°) movement with state memory
  for (int p = 0; p < pulses; p++) {
    int currentPos = servo3.read();
    
    // Toggle state: ขวา(60°) <-> ซ้าย(120°)
    servo3_isLeft = !servo3_isLeft;
    int targetPos = servo3_isLeft ? 120 : 60;
    
    smoothMove(servo3, currentPos, targetPos);
    delay(150); // หน่วงเวลาเปิด (reduced from 300ms)
    
    if (p < pulses - 1) {
      delay(50); // pause between movements (reduced from 100ms)
    }
  }
}

void servoLogic4(int pulses = 1) {
  // Servo 4 - alternating right(60°)/left(120°) movement with state memory
  for (int p = 0; p < pulses; p++) {
    int currentPos = servo4.read();
    
    // Toggle state: ขวา(60°) <-> ซ้าย(120°)
    servo4_isLeft = !servo4_isLeft;
    int targetPos = servo4_isLeft ? 120 : 60;
    
    smoothMove(servo4, currentPos, targetPos);
    delay(180); // หน่วงเวลาเปิด (reduced from 600ms)
    
    if (p < pulses - 1) {
      delay(50); // pause between movements (reduced from 100ms)
    }
  }
}

// ---------- Actuator control functions ----------
void setupActuators() {
  servo1.attach(PIN_SERVO1_OUT);
  servo2.attach(PIN_SERVO2_OUT);
  servo3.attach(PIN_SERVO3_OUT);
  servo4.attach(PIN_SERVO4_OUT);

  // Initialize to starting positions (120° = ซ้าย = starting position)
  servo1.write(120);  // 120° = ซ้าย
  servo2.write(120);  // 120° = ซ้าย
  servo3.write(120);  // 120° = ซ้าย
  servo4.write(120);  // 120° = ซ้าย
  
  // Initialize state tracking (all start at ซ้าย = true)
  servo1_isLeft = true;   // เริ่มที่ซ้าย (120°)
  servo2_isLeft = true;   // เริ่มที่ซ้าย (120°)
  servo3_isLeft = true;   // เริ่มที่ซ้าย (120°)
  servo4_isLeft = true;   // เริ่มที่ซ้าย (120°)

  pinMode(PIN_DC_EN_OUT, OUTPUT);
  digitalWrite(PIN_DC_EN_OUT, LOW);   // OFF initially
}

void setDcState(bool on) {
  dc_running = on;
  digitalWrite(PIN_DC_EN_OUT, on ? HIGH : LOW);
  
  if (on) {
    dc_start_time = millis(); // Record when DC started
    Serial.println("DC Motor: ON - will auto-stop in 15 seconds");
  } else {
    Serial.println("DC Motor: OFF");
  }
}

void controlServo(int servoId, int position) {
  Serial.print("Moving servo ");
  Serial.print(servoId);
  Serial.print(" to position ");
  Serial.println(position);
  
  Servo* targetServo = nullptr;
  
  switch (servoId) {
    case 1: targetServo = &servo1; break;
    case 2: targetServo = &servo2; break;
    case 3: targetServo = &servo3; break;
    case 4: targetServo = &servo4; break;
    default: 
      Serial.print("Invalid servo ID: ");
      Serial.println(servoId);
      return;
  }
  
  int currentPos = targetServo->read();
  smoothMove(*targetServo, currentPos, position);
  Serial.println("Servo movement complete");
}

void actuatePill(int queueId, int pillId, int quantity) {
  Serial.print("Starting pill dispensing - Queue: ");
  Serial.print(queueId);
  Serial.print(", Pill: ");
  Serial.print(pillId);
  Serial.print(", Quantity: ");
  Serial.println(quantity);
  
  // *** AUTO DC ON for any pill request ***
  setDcState(true);
  
  // Direct mapping: pill_id = servo number with alternating movement logic
  if (pillId >= 1 && pillId <= 4) {
    Serial.print("Executing servo logic for pill ");
    Serial.println(pillId);
    
    // Execute servo-specific logic with 1 second delay between each pill
    for (int i = 0; i < quantity; i++) {
      Serial.print("Dispensing pill ");
      Serial.print(i + 1);
      Serial.print(" of ");
      Serial.println(quantity);
      
      // Execute one pulse for this pill
      switch (pillId) {
        case 1: servoLogic1(1); break;  // Always 1 pulse per pill
        case 2: servoLogic2(1); break;
        case 3: servoLogic3(1); break;
        case 4: servoLogic4(1); break;
      }
      
      // Delay 1 second between each pill (except for the last one)
      if (i < quantity - 1) {
        Serial.println("Waiting 1 second before next pill...");
        delay(1000); // 1 second delay between pills
      }
    }
    
    Serial.println("All servo movements complete");
    
    // Send done immediately after servo completion
    nodeSerial.println("done");
    Serial.println("TX -> NodeMCU: done");
    
  } else {
    Serial.print("Invalid pill ID: ");
    Serial.println(pillId);
  }
}

void processCommand(char* command) {
  // Debug: Print received command
  Serial.print("RX <- NodeMCU: ");
  Serial.println(command);
  
  // Parse DC command: "DC,0" or "DC,1"
  if (strncmp(command, "DC,", 3) == 0) {
    int value = atoi(command + 3);
    Serial.print("Processing DC command, value: ");
    Serial.println(value);
    setDcState(value != 0);
    nodeSerial.println("done");
    Serial.println("TX -> NodeMCU: done");
    return;
  }
  
  // Parse SERVO command: "SERVO,id,position"
  if (strncmp(command, "SERVO,", 6) == 0) {
    int servoId, position;
    if (sscanf(command + 6, "%d,%d", &servoId, &position) == 2) {
      Serial.print("Processing SERVO command, id: ");
      Serial.print(servoId);
      Serial.print(", position: ");
      Serial.println(position);
      controlServo(servoId, position);
      nodeSerial.println("done");
      Serial.println("TX -> NodeMCU: done");
      return;
    }
  }
  
  // Parse pill command: "queue_id,pill_id,quantity"
  int queueId, pillId, quantity;
  if (sscanf(command, "%d,%d,%d", &queueId, &pillId, &quantity) == 3) {
    Serial.print("Processing PILL command, queue: ");
    Serial.print(queueId);
    Serial.print(", pill: ");
    Serial.print(pillId);
    Serial.print(", qty: ");
    Serial.println(quantity);
    actuatePill(queueId, pillId, quantity);
  } else {
    Serial.print("Unknown command: ");
    Serial.println(command);
  }
}

// ---------- Setup / Loop ----------
void setup() {
  Serial.begin(9600);     // USB Serial for monitoring
  nodeSerial.begin(9600); // SoftwareSerial for NodeMCU communication
  delay(200);
  Serial.println(F("Arduino ready"));
   
  setupActuators();
  
  // Clear buffer
  memset(serialBuffer, 0, sizeof(serialBuffer));
  bufferIndex = 0;
  
  // Initialize DC state
  dc_running = false;
  dc_start_time = 0;
}

void loop() {
  // Check DC motor auto-stop (15 seconds)
  if (dc_running && (millis() - dc_start_time >= DC_AUTO_STOP_MS)) {
    Serial.println("DC motor auto-stop after 15 seconds");
    setDcState(false);
    nodeSerial.println("done");
  }
  
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
      Serial.println("Buffer overflow - resetting");
      bufferIndex = 0;
    }
  }
  
  // Check for commands from USB Serial for testing
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (bufferIndex > 0) {
        serialBuffer[bufferIndex] = '\0';
        Serial.print("Manual command: ");
        Serial.println(serialBuffer);
        processCommand(serialBuffer);
        bufferIndex = 0;
      }
    } else if (bufferIndex < sizeof(serialBuffer) - 1) {
      serialBuffer[bufferIndex++] = c;
    } else {
      bufferIndex = 0;
    }
  }
}
