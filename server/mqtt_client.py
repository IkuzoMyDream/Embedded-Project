import json
import paho.mqtt.client as mqtt
from .config import MQTT_BROKER, MQTT_PORT, MQTT_CLIENT_ID, MQTT_TOPIC_ACK
from .db import execute

_client = None

def on_connect(client, userdata, flags, rc, properties=None):
    client.subscribe(MQTT_TOPIC_ACK)

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        qid = payload.get("queue_id")
        status = payload.get("status", "success")  # success|failed
        execute("UPDATE queues SET status=?, served_at=CURRENT_TIMESTAMP WHERE id=?", (status, qid))
        execute("INSERT INTO events(queue_id, event, message) VALUES(?,?,?)",
                (qid, "ack", json.dumps(payload)))
    except Exception as e:
        execute("INSERT INTO events(queue_id, event, message) VALUES(?,?,?)",
                (None, "ack_parse_error", str(e)))
 
def get_client():
    global _client
    if _client: return _client
    c = mqtt.Client(client_id=MQTT_CLIENT_ID, clean_session=True)
    c.on_connect = on_connect
    c.on_message = on_message
    c.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    c.loop_start()
    _client = c
    return _client
