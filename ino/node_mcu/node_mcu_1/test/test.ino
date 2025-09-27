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

bool g_online = false;
bool g_ready  = true;   // node starts ready
int activeQueue = -1;   // store current queue id until evt done

// ======= OUTPUT PINS (logic signals to Arduino) =======
const int PIN_SERVO1 = D1; // GPIO5
const int PIN_SERVO2 = D2; // GPIO4
const int PIN_SERVO3 = D5; // GPIO14
const int PIN_SERVO4 = D6; // GPIO12

// pulse duration per dispense action (ms)
const unsigned long PULSE_MS = 200;

const size_t MQTT_BUF = 512;
unsigned long lastHeartbeat = 0;
const unsigned long HEARTBEAT_MS = 5000;

// ======= UTIL =======
void wifiEnsure() {
  if (WiFi.status() == WL_CONNECTED) return;
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("[WiFi] connecting");
  while (WiFi.status() != WL_CONNECTED) {
    delay(300);
    Serial.print(".");
  }
  Serial.printf("\n[WiFi] OK %s\n", WiFi.localIP().toString().c_str());
}

void publishJson(const String& topic, const JsonDocument& doc, bool retain=false) {
  static char buf[MQTT_BUF];
  size_t n = serializeJson(doc, buf, sizeof(buf));
  mqtt.publish(topic.c_str(), (const uint8_t*)buf, (unsigned int)n, retain);
}

void publishState() {
  StaticJsonDocument<128> d;
  d["online"] = g_online ? 1 : 0;
  d["ready"]  = g_ready ? 1 : 0;
  d["uptime"] = (uint32_t)(millis()/1000);
  publishJson(T_STATE, d, /*retain=*/true);   // retain latest state
}

void publishAck(int queueId, bool accepted) {
  StaticJsonDocument<128> d;
  d["queue_id"] = queueId;
  d["accepted"] = accepted ? 1 : 0;
  publishJson(T_ACK, d, false);
}

void publishEvt(int queueId, int sensorVal) {
  StaticJsonDocument<160> d;
  d["queue_id"] = queueId;
  d["done"]     = 1;
  d["status"]   = "success";
  d["sensor"]   = sensorVal;
  publishJson(T_EVT, d, false);
}

// Map pill_id to servo output pin
int pillIdToPin(int pill_id) {
  switch (pill_id) {
    case 1: return PIN_SERVO1;
    case 2: return PIN_SERVO2;
    case 3: return PIN_SERVO3;
    case 4: return PIN_SERVO4;
    default: return -1; // not handled
  }
}

// Actuate pin for dispense: pulse HIGH then LOW. Quantity -> repeat pulses
void actuatePill(int pill_id, int quantity) {
  int pin = pillIdToPin(pill_id);
  if (pin < 0) {
    Serial.printf("[node] pill_id %d not mapped, skipping\n", pill_id);
    return;
  }
  for (int i=0;i<max(1, quantity);++i) {
    digitalWrite(pin, HIGH);
    delay(PULSE_MS);
    digitalWrite(pin, LOW);
    delay(50);
  }
}

// ======= MQTT CALLBACK =======
void onMessage(char* topic, byte* payload, unsigned int len) {
  Serial.printf("[MQTT] %s | %u bytes\n", topic, len);

  // if busy (ready=0), ignore new commands
  if (!g_ready) {
    Serial.println("[node] BUSY, ignoring cmd");
    return;
  }

  StaticJsonDocument<MQTT_BUF> d;
  DeserializationError err = deserializeJson(d, payload, len);
  if (err) { Serial.printf("[JSON] %s\n", err.c_str()); return; }

  int queueId = d["queue_id"] | -1;
  if (queueId < 0) {
    publishAck(queueId, false);
    return;
  }

  // Accept command
  publishAck(queueId, true);
  // if payload contains 'items' array, map pill_id -> servo pin and actuate
  if (d.containsKey("items")) {
    JsonArray items = d["items"].as<JsonArray>();
    Serial.printf("[node] Received items count=%u\n", items.size());
    for (JsonObject it : items) {
      int pid = it["pill_id"] | -1;
      int qty = it["quantity"] | 1;
      Serial.printf("[node] actuate pill_id=%d qty=%d\n", pid, qty);
      actuatePill(pid, qty);
    }
  } else {
    // fallback: older single-op command style {"op":"servo","id":N,"on":1}
    const char* op = d["op"] | "";
    if (op && strcmp(op, "") != 0) {
      if (!strcmp(op, "servo")) {
        int id = d["id"] | -1;
        int on = d["on"] | 0;
        if (id > 0 && on) {
          actuatePill(id, 1);
        }
      }
    }
  }

  activeQueue = queueId;
  g_ready = false;   // lock until sensor confirms
  publishState();
  Serial.printf("[node] Accepted queue=%d, waiting for sensor input...\n", queueId);
}

// ======= SERIAL INPUT =======
void handleSerial() {
  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    if (line.length() == 0) return;

    if (activeQueue >= 0) {
      int val = line.toInt();
      Serial.printf("[node] Sensor triggered: %d\n", val);
      publishEvt(activeQueue, val);
      delay(500);
      g_ready = true;         // unlock
      publishState();
      activeQueue = -1;
    } else {
      Serial.println("[node] No active queue, ignoring input");
    }
  }
}

// ======= MQTT ENSURE =======
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
    g_online = true;
    publishState();   // retained state at connect
  } else {
    Serial.printf("fail rc=%d\n", mqtt.state());
  }
}

// ======= SETUP / LOOP =======
void setup() {
  Serial.begin(115200);
  delay(50);
  Serial.println("\n[node1] boot (test mode)");

  wifiEnsure();
  mqtt.setCallback(onMessage);
  mqttEnsure();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) wifiEnsure();
  if (!mqtt.connected()) mqttEnsure();
  mqtt.loop();

  handleSerial();

  // heartbeat every 5s
  if (millis() - lastHeartbeat > HEARTBEAT_MS) {
    publishState();
    lastHeartbeat = millis();
  }

  delay(10);
}
