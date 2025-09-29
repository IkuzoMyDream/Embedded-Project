// Arduino node2: parse commands from NodeMCU and actuate stepper/servos/pump/DC
// Expected incoming lines (CSV or keyword commands):
//  DIR,L  or DIR,R         -> set stepper direction (L=left/ทวนเข็ม, R=right/ตามเข็ม)
//  SERVO5,1                -> trigger servo5
//  SERVO6,1                -> trigger servo6
//  PUMP,1                  -> turn pump ON (PUMP,0 to stop)
//  DC,1                    -> DC motor on (always triggered after disp/cmd)
//  <queue_id>,<pill_id>,<qty>  -> perform pill actuation, then print DONE

String buffer = "";

// --- stub actuator implementations (replace with real code) ---
void setStepDirectionLeft() {
  Serial.println("[ACT] Stepper dir: LEFT");
}
void setStepDirectionRight() {
  Serial.println("[ACT] Stepper dir: RIGHT");
}

void triggerServo5() {
  Serial.println("[ACT] Servo5 triggered");
}
void triggerServo6() {
  Serial.println("[ACT] Servo6 triggered");
}

void setPump(bool on) {
  Serial.print("[ACT] Pump set to "); Serial.println(on ? 1 : 0);
}

void setDcState(bool on) {
  Serial.print("[ACT] DC set to "); Serial.println(on ? 1 : 0);
}

// Sensor: detect patient receiving medication and notify NodeMCU via UART
const uint8_t PIN_SENSOR = 3; // change to your input pin
bool lastSensorState = false;


void setup() {
  Serial.begin(9600);
  delay(200);
  Serial.println("Arduino2 actuator stub ready (sensor mode)");
  pinMode(PIN_SENSOR, INPUT_PULLUP); // assume sensor pulls LOW normally, HIGH when detected; change if needed
  lastSensorState = digitalRead(PIN_SENSOR);
}

void processLine(const String &lineRaw) {
  String line = lineRaw;
  line.trim();
  if (line.length() == 0) return;

  // Keywords
  if (line.startsWith("DIR,")) {
    char d = line.charAt(4);
    if (d == 'L' || d == 'l') setStepDirectionLeft();
    else setStepDirectionRight();
  // any trigger from NodeMCU: actuate only (no auto-done timer)
  } else if (line.startsWith("SERVO5,")) {
    triggerServo5();
  // actuate only (no auto-done timer)
  } else if (line.startsWith("SERVO6,")) {
    triggerServo6();
  // actuate only (no auto-done timer)
  } else if (line.startsWith("PUMP,")) {
    int v = atoi(line.c_str() + 5);
    setPump(v != 0);
  // actuate only (no auto-done timer)
  } else if (line.startsWith("DC,")) {
    int v = atoi(line.c_str() + 3);
    setDcState(v != 0);
    
    // Test mode: DC,1 triggers simulation completion after delay
    if (v == 1) {
      Serial.println("[TEST] Starting actuator sequence...");
      delay(2000); // simulate processing time
      Serial.println("done");
    }
  } else {
    // unknown line: echo back so NodeMCU can parse sensor values if needed
    Serial.println(line);
  }
}

void loop() {
  // handle incoming Serial commands from NodeMCU
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (buffer.length() == 0) { buffer = ""; continue; }
      processLine(buffer);
      buffer = "";
    } else {
      buffer += c;
      if (buffer.length() > 200) buffer = buffer.substring(buffer.length()-200);
    }
  }

  // poll sensor and send done when detection occurs (rising edge)
  bool cur = digitalRead(PIN_SENSOR);
  if (cur && !lastSensorState) {
    // sensor just triggered
    Serial.println("done");
    Serial.println("1"); // optional numeric indicator
  }
  lastSensorState = cur;


  delay(20); // small debounce / cooperative delay
}
