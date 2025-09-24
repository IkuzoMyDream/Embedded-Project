import json
import logging
import paho.mqtt.client as mqtt
from .config import MQTT_BROKER, MQTT_PORT, MQTT_CLIENT_ID, MQTT_TOPIC_ACK, MQTT_TOPIC_CMD
from .db import execute, query

_logger = logging.getLogger(__name__)
_client = None


def on_connect(client, userdata, flags, rc, properties=None):
    try:
        client.subscribe(MQTT_TOPIC_ACK)
    except Exception as e:
        _logger.exception('subscribe failed: %s', e)


def _publish_next_pending(client):
    try:
        nxt = query("SELECT id, patient_id, target_room FROM queues WHERE status='pending' ORDER BY created_at ASC LIMIT 1")
        if not nxt:
            _logger.debug('No pending queue to publish')
            return
        q = nxt[0]
        items = query("SELECT pill_id,quantity FROM queue_items WHERE queue_id=?", (q['id'],))
        payload = {
            'queue_id': q['id'],
            'patient_id': q['patient_id'],
            'target_room': q['target_room'],
            'items': [{'pill_id': it['pill_id'], 'quantity': it['quantity']} for it in items]
        }
        client.publish(MQTT_TOPIC_CMD, json.dumps(payload), qos=1, retain=False)
        execute("UPDATE queues SET status='sent' WHERE id=?", (q['id'],))
        _logger.info('Published next pending queue %s to device', q['id'])
    except Exception as e:
        _logger.exception('Failed to publish next pending queue: %s', e)


def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        qid = payload.get("queue_id")
        status = payload.get("status", "success")  # expected values: ready|processing|success|failed
        _logger.debug('Received mqtt ack for queue=%s status=%s', qid, status)

        if qid is None:
            _logger.warning('MQTT ack missing queue_id: %s', payload)
            return

        # Normalize status handling
        st = status.lower()
        if st in ('ready', 'accepted'):
            # device indicates it accepted the command and is ready -> mark pending
            execute("UPDATE queues SET status=? WHERE id=?", ('pending', qid))
            execute("INSERT INTO events(queue_id, event, message) VALUES(?,?,?)", (qid, 'ack_ready', json.dumps(payload)))
        elif st in ('processing', 'start'):
            execute("UPDATE queues SET status=? WHERE id=?", ('processing', qid))
            execute("INSERT INTO events(queue_id, event, message) VALUES(?,?,?)", (qid, 'ack_processing', json.dumps(payload)))
        elif st in ('success', 'done'):
            execute("UPDATE queues SET status=?, served_at=CURRENT_TIMESTAMP WHERE id=?", ('success', qid))
            execute("INSERT INTO events(queue_id, event, message) VALUES(?,?,?)", (qid, 'ack', json.dumps(payload)))
            # once success, publish next pending queue (if any)
            _publish_next_pending(client)
        else:
            # unknown status - record and treat as generic ack
            execute("INSERT INTO events(queue_id, event, message) VALUES(?,?,?)", (qid, 'ack_unknown', json.dumps(payload)))
    except Exception as e:
        _logger.exception('failed to handle mqtt message: %s', e)
        try:
            execute("INSERT INTO events(queue_id, event, message) VALUES(?,?,?)", (None, 'ack_parse_error', str(e)))
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
