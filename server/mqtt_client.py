import json
import logging
import paho.mqtt.client as mqtt
from .config import MQTT_BROKER, MQTT_PORT, MQTT_CLIENT_ID, MQTT_TOPIC_ACK
from .db import execute

_logger = logging.getLogger(__name__)
_client = None


def on_connect(client, userdata, flags, rc, properties=None):
    try:
        client.subscribe(MQTT_TOPIC_ACK)
    except Exception as e:
        _logger.exception('subscribe failed: %s', e)


def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        qid = payload.get("queue_id")
        status = payload.get("status", "success")  # success|failed
        execute("UPDATE queues SET status=?, served_at=CURRENT_TIMESTAMP WHERE id=?", (status, qid))
        execute("INSERT INTO events(queue_id, event, message) VALUES(?,?,?)",
                (qid, "ack", json.dumps(payload)))
    except Exception as e:
        _logger.exception('failed to handle mqtt message: %s', e)
        try:
            execute("INSERT INTO events(queue_id, event, message) VALUES(?,?,?)",
                    (None, "ack_parse_error", str(e)))
        except Exception:
            pass


class _DummyClient:
    def __init__(self):
        self._connected = False
    def publish(self, topic, payload, qos=0, retain=False):
        _logger.warning('MQTT publish skipped (no broker): %s %s', topic, payload)
    def subscribe(self, *args, **kwargs):
        _logger.debug('MQTT subscribe skipped (no broker)')


def get_client():
    global _client
    if _client:
        return _client

    try:
        c = mqtt.Client(client_id=MQTT_CLIENT_ID, clean_session=True)
        c.on_connect = on_connect
        c.on_message = on_message
        # attempt connect
        c.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        c.loop_start()
        _client = c
        _logger.info('Connected to MQTT broker %s:%s', MQTT_BROKER, MQTT_PORT)
        return _client
    except Exception as e:
        _logger.warning('Could not connect to MQTT broker %s:%s — proceeding without MQTT (%s)', MQTT_BROKER, MQTT_PORT, e)
        _client = _DummyClient()
        return _client
