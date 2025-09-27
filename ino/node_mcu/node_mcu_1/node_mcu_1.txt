/* node_mcu_1.ino — NodeMCU (ESP8266) nodeId=1
 * Role: รับคำสั่ง MQTT แล้ว "ยิงลอจิก 0/1" ออก 5 ขาไปเข้า Arduino
 *
 * Topics:
 *   Sub: disp/cmd/1
 *     Payload: { "queue_id":<int>, "op":"servo|dc", "id":<1..4?>, "on":<0|1> }
 *   Pub: disp/ack/1  -> { "queue_id":<int>, "accepted":1|0 }
 *        disp/evt/1  -> { "queue_id":<int>, "done":1, "status":"success" }
 *        disp/state/1 (retained) -> { "online":1, "uptime":<sec> }
 *
 * Pin map to Arduino:
 *   D1(GPIO5)  -> servo1 (logic)
 *   D2(GPIO4)  -> servo2 (logic)
 *   D5(GPIO14) -> servo3 (logic)
 *   D6(GPIO12) -> servo4 (logic)
 *   D7(GPIO13) -> dcmotor1_enable (1=run, 0=stop)
 */

#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// ======= USER CONFIG =======
#define WIFI_SSID  "YOUR_WIFI_SSID"
#define WIFI_PASS  "YOUR_WIFI_PASSWORD"
#define MQTT_HOST  "10.0.0.10"     // Odroid IP
#define MQTT_PORT  1883 

static const int NODE_ID = 1;

// Topics
String T_CMD   = "disp/cmd/1";
String T_ACK   = "disp/ack/1";
String T_EVT   = "disp/evt/1";
String T_STATE = "disp/state/1";

// Heartbeat period
const uint32_t STATE_PERIOD_MS = 5000;

// ======= PINS (ESP8266) =======
const int PIN_SERVO1 = D1;  // GPIO5
const int PIN_SERVO2 = D2;  // GPIO4
const int PIN_SERVO3 = D5;  // GPIO14
const int PIN_SERVO4 = D6;  // GPIO12
const int PIN_DC_EN  = D7;  // GPIO13

// ======= GLOBALS =======
WiFiClient wifi;
PubSubClient mqtt(wifi);
char clientId[48];
uint32_t lastStateAt = 0;

// JSON/MQTT buffer
const size_t MQTT_BUF = 512;

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
  // FIX: cast to const uint8_t* to match PubSubClient signature
  mqtt.publish(topic.c_str(), (const uint8_t*)buf, (unsigned int)n, retain);
}

void publishAck(int queueId, bool accepted) {
  StaticJsonDocument<128> d;
  d["queue_id"] = queueId;
  d["accepted"] = accepted ? 1 : 0;
  publishJson(T_ACK, d, false);
}

void publishEvtDone(int queueId, const char* status="success") {
  StaticJsonDocument<160> d;
  d["queue_id"] = queueId;
  d["done"]     = 1;
  d["status"]   = status;
  publishJson(T_EVT, d, false);
}

void publishState() {
  StaticJsonDocument<128> d;
  d["online"] = 1;
  d["uptime"] = (uint32_t)(millis()/1000);
  publishJson(T_STATE, d, /*retain=*/true);
}

void mqttEnsure() {
  if (mqtt.connected()) return;
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setKeepAlive(30);
  mqtt.setBufferSize(MQTT_BUF);  // allow JSON up to MQTT_BUF

  snprintf(clientId, sizeof(clientId), "esp8266-node%d-%06X", NODE_ID, ESP.getChipId());
  Serial.print("[MQTT] connecting... ");
  if (mqtt.connect(clientId)) {
    Serial.println("OK");
    mqtt.subscribe(T_CMD.c_str(), 1);  // QoS1 for commands
    publishState();                    // retained heartbeat
  } else {
    Serial.printf("fail rc=%d\n", mqtt.state());
  }
}

// ======= ACTUATOR LOGIC-ONLY =======
bool setServoLogic(uint8_t id, bool on) {
  switch (id) {
    case 1: digitalWrite(PIN_SERVO1, on ? HIGH : LOW); return true;
    case 2: digitalWrite(PIN_SERVO2, on ? HIGH : LOW); return true;
    case 3: digitalWrite(PIN_SERVO3, on ? HIGH : LOW); return true;
    case 4: digitalWrite(PIN_SERVO4, on ? HIGH : LOW); return true;
    default: return false;
  }
}

void setDcEnable(bool on) {
  digitalWrite(PIN_DC_EN, on ? HIGH : LOW);
}

// ======= MQTT CALLBACK =======
void onMessage(char* topic, byte* payload, unsigned int len) {
  Serial.printf("[MQTT] %s | %u bytes\n", topic, len);

  StaticJsonDocument<MQTT_BUF> d;
  DeserializationError err = deserializeJson(d, payload, len);
  if (err) { Serial.printf("[JSON] %s\n", err.c_str()); return; }

  int queueId = d["queue_id"] | -1;
  const char* op = d["op"] | "";

  if (queueId < 0 || op[0] == '\0') {
    publishAck(queueId, false);
    return;
  }

  // Acknowledge reception first
  publishAck(queueId, true);

  if (!strcmp(op, "servo")) {
    int id = d["id"] | -1;
    int on = d["on"] | 0;
    bool ok = setServoLogic((uint8_t)id, on != 0);
    publishEvtDone(queueId, ok ? "success" : "failed");

  } else if (!strcmp(op, "dc")) {
    int on = d["on"] | 0;
    setDcEnable(on != 0);
    publishEvtDone(queueId, "success");

  } else {
    // ops 'step' and 'pump' are not for node 1; ignore gracefully
    publishEvtDone(queueId, "success");
  }
}

// ======= SETUP / LOOP =======
void setup() {
  Serial.begin(115200);
  delay(50);
  Serial.println("\n[node1] boot (logic-out mode)");

  // Prepare pins as outputs, default LOW
  pinMode(PIN_SERVO1, OUTPUT); digitalWrite(PIN_SERVO1, LOW);
  pinMode(PIN_SERVO2, OUTPUT); digitalWrite(PIN_SERVO2, LOW);
  pinMode(PIN_SERVO3, OUTPUT); digitalWrite(PIN_SERVO3, LOW);
  pinMode(PIN_SERVO4, OUTPUT); digitalWrite(PIN_SERVO4, LOW);
  pinMode(PIN_DC_EN,  OUTPUT); digitalWrite(PIN_DC_EN,  LOW);

  wifiEnsure();
  mqtt.setCallback(onMessage);
  mqttEnsure();
  lastStateAt = millis();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) wifiEnsure();
  if (!mqtt.connected()) mqttEnsure();
  mqtt.loop();

  if (millis() - lastStateAt > STATE_PERIOD_MS) {
    lastStateAt = millis();
    publishState();
  }
  delay(1);
}


















// // ----- ESP8266 + PubSubClient (JSON ACK for Flask) -----
// #include <ESP8266WiFi.h>
// #include <PubSubClient.h>

// // ---- WiFi ----
// const char* WIFI_SSID = "ao";
// const char* WIFI_PASS = "12345678zz";

// // ---- MQTT broker on Odroid ----
// const char* MQTT_HOST = "10.238.101.224";   // Odroid IP
// const uint16_t MQTT_PORT = 1883;

// // ---- Topics (match Flask .env / defaults) ----
// const char* TOPIC_CMD = "dispense/queue/cmd";
// const char* TOPIC_ACK = "dispense/queue/ack";

// // ---- Globals ----
// WiFiClient espClient;
// PubSubClient mqtt(espClient);
// char clientId[40];

// // crude extractor for {"queue_id": N, ...}
// int extractQueueId(const String& s) {
//   int p = s.indexOf("\"queue_id\"");
//   if (p < 0) return -1;
//   p = s.indexOf(':', p);
//   if (p < 0) return -1;
//   // skip colon & spaces
//   while (p < (int)s.length() && (s[p] == ':' || s[p] == ' ')) p++;
//   int start = p;
//   while (p < (int)s.length() && isDigit(s[p])) p++;
//   return s.substring(start, p).toInt();
// }

// void onMessage(char* topic, byte* payload, unsigned int len) {
//   String msg; msg.reserve(len);
//   for (unsigned int i=0; i<len; ++i) msg += (char)payload[i];

//   Serial.printf("[MQTT] %s %s\n", topic, msg.c_str());
//   int qid = extractQueueId(msg);
//   if (qid < 0) {
//     Serial.println("[PARSE] queue_id not found");
//     return;
//   }

//   // TODO: drive servo/conveyor here…
//   delay(1000); // simulate work

//   // Publish ACK JSON exactly as Flask expects
//   String ack = String("{\"queue_id\":") + qid +
//                ",\"status\":\"success\",\"device\":\"esp8266-1\"}";
//   mqtt.publish(TOPIC_ACK, ack.c_str());
//   Serial.printf("[MQTT] ACK -> %s\n", ack.c_str());
// }

// void ensureWifi() {
//   if (WiFi.status() == WL_CONNECTED) return;
//   WiFi.mode(WIFI_STA);
//   WiFi.begin(WIFI_SSID, WIFI_PASS);
//   Serial.print("WiFi connecting");
//   int tries = 0;
//   while (WiFi.status() != WL_CONNECTED) {
//     delay(500);
//     Serial.print(".");
//     if (++tries > 60) { // 30s timeout
//       Serial.println("\nWiFi retry");
//       WiFi.disconnect(true);
//       WiFi.begin(WIFI_SSID, WIFI_PASS);
//       tries = 0;
//     }
//   }
//   Serial.printf("\nWiFi OK %s\n", WiFi.localIP().toString().c_str());
// }

// void ensureMqtt() {
//   if (mqtt.connected()) return;
//   snprintf(clientId, sizeof(clientId), "esp8266-%06X", ESP.getChipId());
//   Serial.print("MQTT connecting… ");
//   // optional: increase buffer for larger JSON
//   mqtt.setBufferSize(512);
//   if (mqtt.connect(clientId)) {
//     Serial.println("OK");
//     mqtt.subscribe(TOPIC_CMD);
//     Serial.printf("Subscribed: %s\n", TOPIC_CMD);
//   } else {
//     Serial.printf("fail rc=%d\n", mqtt.state());
//   }
// }

// void setup() {
//   Serial.begin(115200);
//   delay(50);
//   ensureWifi();
//   mqtt.setServer(MQTT_HOST, MQTT_PORT);
//   mqtt.setCallback(onMessage);
//   ensureMqtt();
// }

// void loop() {
//   if (WiFi.status() != WL_CONNECTED) ensureWifi();
//   if (!mqtt.connected()) ensureMqtt();
//   mqtt.loop();
//   delay(10);
// }
