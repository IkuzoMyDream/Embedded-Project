// Arduino test stub: parse CSV commands from NodeMCU and forward sensor lines back to NodeMCU

int pill_id = 0;
int qty = 0;
String buffer = "";

// outputs to actuators (kept for reference)
const uint8_t PIN_SERVO1_OUT = 9;
const uint8_t PIN_SERVO2_OUT = 10;
const uint8_t PIN_SERVO3_OUT = 11;
const uint8_t PIN_SERVO4_OUT = 12;

// DC motor outputs
const uint8_t PIN_DC_EN_OUT  = 8;  // ON/OFF enable line to your motor driver
const uint8_t PIN_DC_DIR_OUT = 7;  // optional direction

// state for DC
bool dc_state = false;

void setDcState(bool on) {
  dc_state = on;
  pinMode(PIN_DC_EN_OUT, OUTPUT);
  digitalWrite(PIN_DC_EN_OUT, on ? HIGH : LOW);
  Serial.print("DC state set to "); Serial.println(on ? 1 : 0);
}

void actuatePill(int pid, int quantity) {
  // Test stub: simulate pill dispensing
  Serial.print("[stub] Actuating pill_id="); Serial.print(pid);
  Serial.print(" qty="); Serial.println(quantity);
  
  // Simulate processing time
  delay(1000);
  
  // Signal completion to NodeMCU
  Serial.println("done");
}

void setup() {
  Serial.begin(9600);   // must match NodeMCU
  delay(200);
  Serial.println("Arduino test stub ready");
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (buffer.length() == 0) { buffer = ""; continue; }

      // support DC control: "DC,0" or "DC,1"
      if (buffer.startsWith("DC,")) {
        int v = atoi(buffer.c_str() + 3);
        setDcState(v != 0);

      } else {
        // try parse queue_id,pill_id,qty
        int queue_id = -1;
        int pid = 0;
        int q = 0;
        int parsed = sscanf(buffer.c_str(), "%d,%d,%d", &queue_id, &pid, &q);
        if (parsed == 3) {
          Serial.print("Received queue_id="); Serial.print(queue_id);
          Serial.print(" pill_id="); Serial.print(pid);
          Serial.print(" qty="); Serial.println(q);
          actuatePill(pid, q);
        } else {
          // try pill_id,qty
          parsed = sscanf(buffer.c_str(), "%d,%d", &pid, &q);
          if (parsed == 2) {
            Serial.print("Received pill_id="); Serial.print(pid);
            Serial.print(" qty="); Serial.println(q);
            actuatePill(pid, q);
          } else {
            // If the line is not a command, treat it as a sensor reading string and
            // forward it out so NodeMCU (connected on the same UART) can receive it.
            Serial.println(buffer); // NodeMCU will RX this and handle as sensor
          }
        }
      }

      buffer = "";
    }else {
      buffer += c;
    }   
  } 
  } 
