#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// ======= USER CONFIG =======
#define WIFI_SSID  "HAZANO.my"
#define WIFI_PASS  "winwinwin"
#define MQTT_HOST  "172.20.10.2"     // Odroid IP
#define MQTT_PORT  1883 

static const int NODE_ID = 1;

// MQTT Topics
String T_CMD   = "disp/cmd/1";
String T_ACK   = "disp/ack/1";
String T_EVT   = "disp/evt/1";
String T_STATE = "disp/state/1";

// ======= GLOBALS =======
WiFiClient wifi;
PubSubClient mqtt(wifi);
char clientId[48];

const size_t MQTT_BUF = 1024;
const size_t JSON_CAP = 512;

bool g_online = false;
bool g_ready = true;
int activeQueue = -1;
uint32_t lastReadyPub = 0;
unsigned long lastHeartbeat = 0;
const unsigned long HEARTBEAT_MS = 5000;

// Timeout handling
unsigned long cmdSentTime = 0;
const unsigned long CMD_TIMEOUT_MS = 30000; // 30 seconds timeout

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
}
  
// publish event with optional status ("success" or "failed")
void publishEvt(int queueId, int sensorVal, const char* status="success") {
  StaticJsonDocument<160> d;
  d["queue_id"] = queueId;
  d["done"]     = 1;
  d["status"]   = status;
  d["sensor"]   = sensorVal;
  publishJson(T_EVT, d, false);
}

void forwardToArduino(int queueId, int pill_id, int qty) {
  // CSV format: queue_id,pill_id,quantity\n
  Serial.print(queueId);
  Serial.print(",");
  Serial.print(pill_id);
  Serial.print(",");
  Serial.println(qty);
}

// forward declaration to satisfy compiler/prototype generation
void publishStateCombined(bool retainCombined);

void onMessage(char* topic, byte* payload, unsigned int len) {
  Serial.printf("[MQTT] %s | %u bytes\n", topic, len);
  // allow processing even if g_ready is false; server will sync readiness if needed

  DynamicJsonDocument d(JSON_CAP);
  DeserializationError err = deserializeJson(d, payload, len);
  if (err) { Serial.printf("[JSON] %s\n", err.c_str()); return; }

  // determine if this message is an event/notification or a command
  bool isEvt = (strstr(topic, "/evt/") != NULL);

  if (isEvt) {
    // evt messages are not used in independent mode - ignore all
    return;
  }

  // Otherwise treat as disp/cmd (command)
  int queueId = d["queue_id"] | -1;
  if (queueId < 0) {
    publishAck(queueId, false);
    return;
  }

  // Acknowledge reception and mark busy
  publishAck(queueId, true);
  // mark node not ready while processing
  g_ready = false;
  // publish combined state so server sees not-ready
  StaticJsonDocument<128> stn; stn["online"] = 1; stn["ready"] = 0; stn["uptime"] = (uint32_t)(millis()/1000);
  publishJson(T_STATE, stn, false);
  activeQueue = queueId;
  cmdSentTime = millis(); // Start timeout timer

  // forward either items[] or single pill_id
  if (d.containsKey("items")) {
    JsonArray items = d["items"].as<JsonArray>();
    for (JsonObject it : items) {
      int pid = it["pill_id"] | -1;
      int qty = it["quantity"] | 1;
      Serial.printf("[node] forward pill_id=%d qty=%d\n", pid, qty);
      forwardToArduino(activeQueue, pid, qty);
      delay(100);
    }
  } else if (d.containsKey("pill_id")) {
    int pid = d["pill_id"] | -1;
    int qty = d["quantity"] | 1;
    Serial.printf("[node] forward single pill_id=%d qty=%d\n", pid, qty);
    forwardToArduino(activeQueue, pid, qty);
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
    mqtt.subscribe(T_CMD.c_str(), 1);
    // independent mode - only listen to own command topic
    g_online = true;
    // publish initial state
    StaticJsonDocument<128> s;
    s["online"] = 1;
    s["ready"] = 1;
    s["uptime"] = (uint32_t)(millis()/1000);
    publishJson(T_STATE, s, true); // retained
  } else {
    Serial.printf("fail rc=%d\n", mqtt.state());
  }
}

// publish combined online+ready (non-retained)
void publishStateCombined(bool retainCombined=false) {
  StaticJsonDocument<128> d;
  d["online"] = g_online ? 1 : 0;
  d["ready"] = g_ready ? 1 : 0;
  d["uptime"] = (uint32_t)(millis()/1000);
  publishJson(T_STATE, d, retainCombined);
}

// publish retained online marker
void publishOnlineRetained() {
  StaticJsonDocument<128> d;
  d["online"] = 1;
  d["uptime"] = (uint32_t)(millis()/1000);
  publishJson(T_STATE, d, true);
}

String serialBuffer = "";

void processSerialLine(const String &line) {
  String s = line;
  s.trim();
  if (s.length() == 0) return;
  
  // If Arduino reports "done" we mark queue done and publish event
  if (s.equalsIgnoreCase("done")) {
    if (activeQueue >= 0) {
      Serial.printf("[node1] Arduino done for queue %d\n", activeQueue);
      publishEvt(activeQueue, 0, "success");
      g_ready = true;
      activeQueue = -1;
      cmdSentTime = 0; // Clear timeout timer
      publishStateCombined(false);
    }
    return;
  }
  
  // otherwise try parse numeric sensor value and forward as event
  int val = atoi(s.c_str());
  if (val != 0 || s == "0") {
    if (activeQueue >= 0) {
      publishEvt(activeQueue, val, "success");
    }
  }
}

void setup() {
  Serial.begin(9600);
  delay(500);
  Serial.println("NodeMCU MQTT->Serial forwarder ready! (node 1)");

  wifiEnsure();
  mqtt.setCallback(onMessage);
  mqttEnsure();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) wifiEnsure();
  if (!mqtt.connected()) mqttEnsure();
  mqtt.loop();

  // read lines from Serial (Arduino) and process
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n' || c == '\r') {
      if (serialBuffer.length() > 0) {
        processSerialLine(serialBuffer);
        serialBuffer = "";
      }
    } else {
      serialBuffer += c;
      // prevent runaway
      if (serialBuffer.length() > 200) serialBuffer = serialBuffer.substring(serialBuffer.length()-200);
    }
  }

  // Check for Arduino timeout
  if (activeQueue >= 0 && cmdSentTime > 0 && millis() - cmdSentTime > CMD_TIMEOUT_MS) {
    Serial.printf("[node1] Arduino timeout for queue %d after %d ms\n", activeQueue, CMD_TIMEOUT_MS);
    publishEvt(activeQueue, 0, "timeout");
    g_ready = true;
    activeQueue = -1;
    cmdSentTime = 0;
    publishStateCombined(false);
  }

  // heartbeat: broadcast combined state periodically so server sees node presence/readiness
  if (millis() - lastHeartbeat > HEARTBEAT_MS) {
    lastHeartbeat = millis();
    publishStateCombined(false);
  }
}
