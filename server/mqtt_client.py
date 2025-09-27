import json
import logging
import paho.mqtt.client as mqtt
from .config import MQTT_BROKER, MQTT_PORT, MQTT_CLIENT_ID, MQTT_TOPIC_ACK, MQTT_TOPIC_CMD, MQTT_TOPIC_EVT, MQTT_TOPIC_STATE
from .db import execute, query

_logger = logging.getLogger(__name__)
_client = None

# in-memory node readiness (node_id -> bool)
_node_ready = {}
# in-memory node online presence
_node_online = {}


def on_connect(client, userdata, flags, rc, properties=None):
    try:
        # subscribe to ack/evt/state topics (wildcards expected)
        client.subscribe(MQTT_TOPIC_ACK)
        try:
            client.subscribe(MQTT_TOPIC_EVT)
        except Exception:
            pass
        try:
            client.subscribe(MQTT_TOPIC_STATE)
        except Exception:
            pass
    except Exception as e:
        _logger.exception('subscribe failed: %s', e)


def _publish_next_pending(client):
    try:
        # strict FIFO: เลือก pending id ต่ำสุดก่อน
        nxt = query("SELECT id, patient_id, target_room FROM queues WHERE status='pending' ORDER BY id ASC LIMIT 1")
        if not nxt:
            _logger.debug('No pending queue to publish')
            return
        q = nxt[0]
        # atomic claim: update status only if still pending
        updated = execute("UPDATE queues SET status='in_progress' WHERE id=? AND status='pending'", (q['id'],))
        if not updated:
            _logger.debug('Queue id=%s already claimed by another node, skipping', q['id'])
            return
        items = query("SELECT pill_id,quantity FROM queue_items WHERE queue_id=?", (q['id'],))
        payload = {
            'queue_id': q['id'],
            'patient_id': q['patient_id'],
            'target_room': q['target_room'],
            'items': [{'pill_id': it['pill_id'], 'quantity': it['quantity']} for it in items]
        }
        # decide node id from target_room (default mapping)
        node_id = 1 if q['target_room'] == 1 else 2
        topic = f"disp/cmd/{node_id}"
        client.publish(topic, json.dumps(payload), qos=1, retain=False)
        _logger.info('Published pending queue %s to %s', q['id'], topic)
    except Exception as e:
        _logger.exception('Failed to publish next pending queue: %s', e)


def _publish_pending_for_node(client, node_id):
    try:
        # strict FIFO: เลือก pending id ต่ำสุดก่อน
        nxt = query("SELECT id, patient_id, target_room FROM queues WHERE status='pending' ORDER BY id ASC LIMIT 1")
        if not nxt:
            _logger.debug('No pending queue for any node')
            return
        q = nxt[0]
        # atomic claim: update status only if still pending
        updated = execute("UPDATE queues SET status='in_progress' WHERE id=? AND status='pending'", (q['id'],))
        if not updated:
            _logger.debug('Queue id=%s already claimed by another node, skipping', q['id'])
            return
        items = query("SELECT pill_id,quantity FROM queue_items WHERE queue_id=?", (q['id'],))
        payload = {
            'queue_id': q['id'],
            'patient_id': q['patient_id'],
            'target_room': q['target_room'],
            'items': [{'pill_id': it['pill_id'], 'quantity': it['quantity']} for it in items]
        }
        topic = f"disp/cmd/{node_id}"
        client.publish(topic, json.dumps(payload), qos=1, retain=False)
        _logger.info('Published pending queue %s to %s', q['id'], topic)
    except Exception as e:
        _logger.exception('Failed to publish pending for node %s: %s', node_id, e)


def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        topic = msg.topic
        # try to extract node id from topic suffix (disp/ack/{nodeId}, disp/evt/{nodeId}, disp/state/{nodeId})
        parts = topic.split('/')
        node_id = None
        if len(parts) >= 3:
            try:
                node_id = int(parts[-1])
            except Exception:
                node_id = None

        # ACK: {"queue_id":..., "accepted":1}
        if 'accepted' in payload:
            qid = payload.get('queue_id')
            if qid is None:
                _logger.warning('ACK missing queue_id: %s', payload)
            else:
                accepted = int(payload.get('accepted', 0))
                if accepted:
                    execute("UPDATE queues SET status=? WHERE id=?", ('in_progress', qid))
                    execute("INSERT INTO events(queue_id, event, message) VALUES(?,?,?)", (qid, 'ack_accepted', json.dumps(payload)))
                else:
                    execute("UPDATE queues SET status=? WHERE id=?", ('failed', qid))
                    execute("INSERT INTO events(queue_id, event, message) VALUES(?,?,?)", (qid, 'ack_rejected', json.dumps(payload)))
            return

        # EVT: {"queue_id":..., "done":1, "status":"success", "room":<id>}
        if 'done' in payload and int(payload.get('done', 0)) == 1:
            qid = payload.get('queue_id')
            st = payload.get('status', 'success').lower()
            if qid is None:
                _logger.warning('EVT missing queue_id: %s', payload)
            else:
                if st in ('success', 'ok'):
                    execute("UPDATE queues SET status=?, served_at=CURRENT_TIMESTAMP WHERE id=?", ('success', qid))
                    execute("INSERT INTO events(queue_id, event, message) VALUES(?,?,?)", (qid, 'evt_done', json.dumps(payload)))
                else:
                    execute("UPDATE queues SET status=? WHERE id=?", ('failed', qid))
                    execute("INSERT INTO events(queue_id, event, message) VALUES(?,?,?)", (qid, 'evt_failed', json.dumps(payload)))
                # After EVT, give node a moment; when node reports ready it will trigger next
            return

        # STATE: node readiness / online publish handled below (payload may include 'online' and/or 'ready')
        if 'ready' in payload or 'online' in payload:
            # interpret online / ready separately
            online = int(payload.get('online', 0))
            ready = int(payload.get('ready', 0))
            if node_id is not None:
                _node_online[node_id] = bool(online)
                _node_ready[node_id] = bool(ready)
                # record both values in events for debugging/audit
                execute("INSERT INTO events(queue_id, event, message) VALUES(?,?,?)", (None, 'node_state', json.dumps({'node': node_id, 'online': online, 'ready': ready})))
                _logger.info('Node %s reported online=%s ready=%s', node_id, online, ready)
                if ready:
                    # publish next pending queue for this node
                    _publish_pending_for_node(client, node_id)
            return

        # Unknown payload: try to log with optional queue_id
        qid = payload.get('queue_id')
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
