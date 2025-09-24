// ----- ESP8266 + PubSubClient (JSON ACK for Flask) -----
#include <ESP8266WiFi.h>
#include <PubSubClient.h>

// ---- WiFi ----
const char* WIFI_SSID = "ao";
const char* WIFI_PASS = "12345678zz";

// ---- MQTT broker on Odroid ----
const char* MQTT_HOST = "10.238.101.224";   // Odroid IP
const uint16_t MQTT_PORT = 1883;

// ---- Topics (match Flask .env / defaults) ----
const char* TOPIC_CMD = "dispense/queue/cmd";
const char* TOPIC_ACK = "dispense/queue/ack";

// ---- Globals ----
WiFiClient espClient;
PubSubClient mqtt(espClient);
char clientId[40];

// crude extractor for {"queue_id": N, ...}
int extractQueueId(const String& s) {
  int p = s.indexOf("\"queue_id\"");
  if (p < 0) return -1;
  p = s.indexOf(':', p);
  if (p < 0) return -1;
  // skip colon & spaces
  while (p < (int)s.length() && (s[p] == ':' || s[p] == ' ')) p++;
  int start = p;
  while (p < (int)s.length() && isDigit(s[p])) p++;
  return s.substring(start, p).toInt();
}

void onMessage(char* topic, byte* payload, unsigned int len) {
  String msg; msg.reserve(len);
  for (unsigned int i=0; i<len; ++i) msg += (char)payload[i];

  Serial.printf("[MQTT] %s %s\n", topic, msg.c_str());
  int qid = extractQueueId(msg);
  if (qid < 0) {
    Serial.println("[PARSE] queue_id not found");
    return;
  }

  // TODO: drive servo/conveyor here…
  delay(1000); // simulate work

  // Publish ACK JSON exactly as Flask expects
  String ack = String("{\"queue_id\":") + qid +
               ",\"status\":\"success\",\"device\":\"esp8266-1\"}";
  mqtt.publish(TOPIC_ACK, ack.c_str());
  Serial.printf("[MQTT] ACK -> %s\n", ack.c_str());
}

void ensureWifi() {
  if (WiFi.status() == WL_CONNECTED) return;
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("WiFi connecting");
  int tries = 0;
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
    if (++tries > 60) { // 30s timeout
      Serial.println("\nWiFi retry");
      WiFi.disconnect(true);
      WiFi.begin(WIFI_SSID, WIFI_PASS);
      tries = 0;
    }
  }
  Serial.printf("\nWiFi OK %s\n", WiFi.localIP().toString().c_str());
}

void ensureMqtt() {
  if (mqtt.connected()) return;
  snprintf(clientId, sizeof(clientId), "esp8266-%06X", ESP.getChipId());
  Serial.print("MQTT connecting… ");
  // optional: increase buffer for larger JSON
  mqtt.setBufferSize(512);
  if (mqtt.connect(clientId)) {
    Serial.println("OK");
    mqtt.subscribe(TOPIC_CMD);
    Serial.printf("Subscribed: %s\n", TOPIC_CMD);
  } else {
    Serial.printf("fail rc=%d\n", mqtt.state());
  }
}

void setup() {
  Serial.begin(115200);
  delay(50);
  ensureWifi();
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(onMessage);
  ensureMqtt();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) ensureWifi();
  if (!mqtt.connected()) ensureMqtt();
  mqtt.loop();
  delay(10);
}
