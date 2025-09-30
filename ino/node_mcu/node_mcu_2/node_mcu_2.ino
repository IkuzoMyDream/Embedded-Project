/* node_mcu_2.ino — NodeMCU (ESP8266) nodeId=2
 * Role: Receive MQTT commands and forward to Arduino via SoftwareSerial communication
 * Communication: NodeMCU sends commands to Arduino, waits for "done" response
 *
 * Hardware connections:
 *   NodeMCU TX (D6/GPIO12) -> Arduino Pin 2 (RX)
 *   NodeMCU RX (D7/GPIO13) -> Arduino Pin 3 (TX)
 *   GND -> GND
 *   Both devices can be connected to USB separately for programming/monitoring
 *
 * Topics:
 *   Sub: disp/cmd/2
 *     Payload: { "queue_id":<int>, "target_room":<1|2|3> }
 *   Pub: disp/ack/2  -> { "queue_id":<int>, "accepted":1|0 }
 *        disp/evt/2  -> { "queue_id":<int>, "done":1, "status":"success" }
 *        disp/state/2 (retained) -> { "online":1, "ready":1, "uptime":<sec> }
 *
 * Serial Protocol with Arduino:
 *   Send: "DIR,L/R" or "SERVO5,1" or "SERVO6,1" or "PUMP,1/0" or "DC,1/0"
 *   Receive: "done" when Arduino completes operation
 */

#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <SoftwareSerial.h>

// ======= USER CONFIG =======
#define WIFI_SSID  "HAZANO.my"
#define WIFI_PASS  "winwinwin"
#define MQTT_HOST  "172.20.10.2"     // Odroid IP
#define MQTT_PORT  1883 

static const int NODE_ID = 2;

// Hardware pins for Arduino communication
const int PIN_TX_TO_ARDUINO = D6;  // GPIO12 - NodeMCU TX -> Arduino Pin 2 (RX)
const int PIN_RX_FROM_ARDUINO = D7; // GPIO13 - NodeMCU RX -> Arduino Pin 3 (TX)

// Topics
String T_CMD   = "disp/cmd/2";
String T_ACK   = "disp/ack/2";
String T_EVT   = "disp/evt/2";
String T_STATE = "disp/state/2";

// Heartbeat period
const uint32_t STATE_PERIOD_MS = 5000;
const uint32_t READY_BROADCAST_MS = 2000;

// ======= GLOBALS =======
WiFiClient wifi;
PubSubClient mqtt(wifi);
SoftwareSerial arduinoSerial(PIN_RX_FROM_ARDUINO, PIN_TX_TO_ARDUINO); // RX, TX
char clientId[48];
uint32_t lastStateAt = 0;

// Node state
bool g_online = false;
bool g_ready = true;
int activeQueue = -1;
uint32_t lastReadyPub = 0;

// Arduino communication
unsigned long cmdSentTime = 0;
const unsigned long CMD_TIMEOUT_MS = 30000; // 30 seconds timeout
String serialBuffer = "";
int pendingCommands = 0; // Track number of commands sent to Arduino

// JSON/MQTT buffer
const size_t MQTT_BUF = 1024;
const size_t JSON_CAP = 512;

// ======= UTIL =======
void wifiEnsure() {
  if (WiFi.status() == WL_CONNECTED) return;
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("[WiFi] connecting");
  int tries = 0;
  while (WiFi.status() != WL_CONNECTED) {
    delay(300);
    Serial.print(".");
    if (++tries > 100) {
      Serial.println("\n[WiFi] retry");
      WiFi.disconnect(true);
      WiFi.begin(WIFI_SSID, WIFI_PASS);
      tries = 0;
    }
  }
  Serial.printf("\n[WiFi] OK %s\n", WiFi.localIP().toString().c_str());
}

void publishJson(const String& topic, const JsonDocument& doc, bool retain=false) {
  static char buf[MQTT_BUF];
  size_t n = serializeJson(doc, buf, sizeof(buf));
  mqtt.publish(topic.c_str(), (const uint8_t*)buf, (unsigned int)n, retain);
}

void publishAck(int queueId, bool accepted) {
  StaticJsonDocument<128> d;
  d["queue_id"] = queueId;
  d["accepted"] = accepted ? 1 : 0;
  publishJson(T_ACK, d, false);
  Serial.printf("[MQTT] ACK sent - queue_id=%d accepted=%d\n", queueId, accepted ? 1 : 0);
}

void publishEvtDone(int queueId, const char* status="success") {
  StaticJsonDocument<160> d;
  d["queue_id"] = queueId;
  d["done"]     = 1;
  d["status"]   = status;
  publishJson(T_EVT, d, false);
  Serial.printf("[MQTT] EVT sent - queue_id=%d status=%s\n", queueId, status);
}

// publish retained online-only (keep a retained marker for presence)
void publishOnlineRetained() {
  StaticJsonDocument<128> d;
  d["online"] = 1;
  d["uptime"] = (uint32_t)(millis()/1000);
  publishJson(T_STATE, d, /*retain=*/true);
}

// publish combined online+ready state
void publishStateCombined(bool retainCombined=false) {
  StaticJsonDocument<128> d;
  d["online"] = g_online ? 1 : 0;
  d["ready"]  = g_ready ? 1 : 0;
  d["uptime"] = (uint32_t)(millis()/1000);
  publishJson(T_STATE, d, /*retain=*/retainCombined);
}

// publish ready flag (node is idle and can accept next queue)
void publishReady(bool ready) {
  g_ready = ready;
  publishStateCombined(false);
  if (ready) {
    lastReadyPub = millis();
    Serial.println("[STATE] Node ready for new commands");
  } else {
    Serial.println("[STATE] Node busy processing command");
  }
}

void mqttEnsure() {
  if (mqtt.connected()) return;
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setKeepAlive(30);
  mqtt.setBufferSize(MQTT_BUF);

  snprintf(clientId, sizeof(clientId), "esp8266-node%d-%06X", NODE_ID, ESP.getChipId());
  Serial.print("[MQTT] connecting... ");
  if (mqtt.connect(clientId)) {
    Serial.println("OK");
    mqtt.subscribe(T_CMD.c_str(), 1);  // QoS1 for commands
    // announce presence: retained online marker
    g_online = true;
    publishOnlineRetained();
    // announce ready to accept work
    publishReady(true);
  } else {
    Serial.printf("fail rc=%d\n", mqtt.state());
  }
}

// ======= ARDUINO COMMUNICATION =======
void sendToArduino(const String& command) {
  Serial.print("[ARDUINO] Sending: ");
  Serial.println(command);
  arduinoSerial.println(command); // Send to Arduino via SoftwareSerial
  pendingCommands++; // Increment pending commands counter
  if (cmdSentTime == 0) {
    cmdSentTime = millis(); // Start timeout timer on first command
  }
}

void processSerialResponse(const String& response) {
  String resp = response;
  resp.trim();
  
  if (resp.length() == 0) return;
  
  Serial.print("[ARDUINO] Response: ");
  Serial.println(resp);
  
  if (resp.equalsIgnoreCase("done")) {
    pendingCommands--; // Decrement pending commands
    Serial.printf("[NODE] Arduino response received, pending: %d\n", pendingCommands);
    
    // Only complete the queue when all commands are done
    if (pendingCommands <= 0 && activeQueue >= 0) {
      Serial.printf("[NODE] All Arduino commands completed for queue %d\n", activeQueue);
      publishEvtDone(activeQueue, "success");
      activeQueue = -1;
      cmdSentTime = 0; // Clear timeout timer
      pendingCommands = 0; // Reset counter
      publishReady(true);
    }
  } else if (resp.equalsIgnoreCase("sensor_done")) {
    // Handle sensor completion separately
    if (activeQueue >= 0) {
      Serial.printf("[NODE] Sensor completion for queue %d\n", activeQueue);
      publishEvtDone(activeQueue, "success");
      activeQueue = -1;
      cmdSentTime = 0;
      pendingCommands = 0;
      publishReady(true);
    }
  } else {
    // Handle other responses (sensor data, status, etc.)
    Serial.printf("[NODE] Arduino data: %s\n", resp.c_str());
  }
}

// ======= MQTT CALLBACK =======
void onMessage(char* topic, byte* payload, unsigned int len) {
  Serial.printf("[MQTT] %s | %u bytes\n", topic, len);

  DynamicJsonDocument d(JSON_CAP);
  DeserializationError err = deserializeJson(d, payload, len);
  if (err) { 
    Serial.printf("[JSON] Error: %s\n", err.c_str()); 
    return; 
  }

  int queueId = d["queue_id"] | -1;
  int targetRoom = d["target_room"] | -1;

  if (queueId < 0) {
    publishAck(queueId, false);
    return;
  }

  // Acknowledge reception first
  publishAck(queueId, true);
  // mark node busy
  publishReady(false);
  activeQueue = queueId;
  pendingCommands = 0; // Reset pending commands counter

  Serial.printf("[NODE] Processing queue %d for target_room %d\n", queueId, targetRoom);

  // Based on target_room, send commands to Arduino
  // Direction: room 1 -> left (L), room 2/3 -> right (R)
  if (targetRoom == 1) {
    sendToArduino("DIR,L");
  } else if (targetRoom == 2 || targetRoom == 3) {
    sendToArduino("DIR,R");
  }

  // Trigger room-specific actuators
  if (targetRoom == 2) {
    sendToArduino("SERVO5,1");
  } else if (targetRoom == 3) {
    sendToArduino("SERVO6,1");
    sendToArduino("PUMP,1");
  }

  // Force completion for testing
  if (d.containsKey("force")) {
    Serial.printf("[NODE] Force completing queue %d\n", queueId);
    publishEvtDone(queueId, "success");
    activeQueue = -1;
    cmdSentTime = 0;
    pendingCommands = 0;
    publishReady(true);
    return;
  }

  // Always trigger DC motor after dispatch command (this will complete the sequence)
  sendToArduino("DC,1");
  
  Serial.printf("[NODE] Sent %d commands to Arduino, waiting for responses...\n", pendingCommands);
}

// ======= SETUP / LOOP =======
void setup() {
  Serial.begin(9600);         // USB Serial for monitoring
  arduinoSerial.begin(9600);  // SoftwareSerial for Arduino communication
  delay(500);
  Serial.println("\n[NODE2] Production MQTT->Arduino bridge starting");
  Serial.println("[NODE2] Using SoftwareSerial - TX:D6(GPIO12), RX:D7(GPIO13)");

  wifiEnsure();
  mqtt.setCallback(onMessage);
  mqttEnsure();
  lastStateAt = millis();
  
  Serial.println("[NODE2] Ready to receive MQTT commands and forward to Arduino");
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) wifiEnsure();
  if (!mqtt.connected()) mqttEnsure();
  mqtt.loop();

  // Read responses from Arduino via SoftwareSerial
  while (arduinoSerial.available()) {
    char c = arduinoSerial.read();
    if (c == '\n' || c == '\r') {
      if (serialBuffer.length() > 0) {
        processSerialResponse(serialBuffer);
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

  // Check for Arduino timeout
  if (activeQueue >= 0 && cmdSentTime > 0 && millis() - cmdSentTime > CMD_TIMEOUT_MS) {
    Serial.printf("[NODE] Arduino timeout for queue %d after %lu ms\n", activeQueue, CMD_TIMEOUT_MS);
    publishEvtDone(activeQueue, "timeout");
    activeQueue = -1;
    cmdSentTime = 0;
    pendingCommands = 0;
    publishReady(true);
  }

  // Periodic retained online heartbeat
  if (millis() - lastStateAt > STATE_PERIOD_MS) {
    lastStateAt = millis();
    publishOnlineRetained();
  }

  // While ready, keep broadcasting combined online+ready more frequently
  if (g_ready && (millis() - lastReadyPub > READY_BROADCAST_MS)) {
    lastReadyPub = millis();
    publishStateCombined(false);
  }
  
  delay(1);
}