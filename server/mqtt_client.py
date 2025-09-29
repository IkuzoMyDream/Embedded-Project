import json
import logging
import paho.mqtt.client as mqtt
import time
from .config import MQTT_BROKER, MQTT_PORT, MQTT_CLIENT_ID, MQTT_TOPIC_ACK, MQTT_TOPIC_CMD, MQTT_TOPIC_EVT, MQTT_TOPIC_STATE
from .db import execute, query, get_conn

_logger = logging.getLogger(__name__)
_client = None

# in-memory node readiness (node_id -> bool)
_node_ready = {}
# in-memory node online presence
_node_online = {}


def on_connect(client, userdata, flags, rc, properties=None):
    try:
        _logger.info('MQTT connected with result code %s', rc)
        # subscribe to ack/evt/state topics (wildcards expected)
        _logger.info('Raw topic values - ACK: "%s", EVT: "%s", STATE: "%s"', MQTT_TOPIC_ACK, MQTT_TOPIC_EVT, MQTT_TOPIC_STATE)
        _logger.info('Subscribing to topics: %s, %s, %s', MQTT_TOPIC_ACK, MQTT_TOPIC_EVT, MQTT_TOPIC_STATE)
        result_ack = client.subscribe(MQTT_TOPIC_ACK)
        result_evt = client.subscribe(MQTT_TOPIC_EVT) 
        result_state = client.subscribe(MQTT_TOPIC_STATE)
        _logger.info('Subscribe results - ACK: %s, EVT: %s, STATE: %s', result_ack, result_evt, result_state)
        _logger.info('Successfully subscribed to MQTT topics')
    except Exception as e:
        _logger.exception('subscribe failed: %s', e)


# Removed _publish_next_pending - using centralized _dispatch_next_queue instead


def _check_both_nodes_ready():
    """Check if both nodes are ready for new commands"""
    return _node_ready.get(1, False) and _node_ready.get(2, False)


def _dispatch_next_queue(client):
    """Dispatch next pending queue to both nodes simultaneously (FIFO strict)"""
    try:
        _logger.info('_dispatch_next_queue called')
        # Check if both nodes are ready
        if not _check_both_nodes_ready():
            _logger.info('Dispatch skipped - Nodes not both ready - Node1: %s, Node2: %s', 
                         _node_ready.get(1, False), _node_ready.get(2, False))
            return False
            
        # Get next pending queue (FIFO strict)
        nxt = query("SELECT id, patient_id, target_room FROM queues WHERE status='pending' ORDER BY id ASC LIMIT 1")
        if not nxt:
            _logger.info('No pending queue to dispatch')
            return False
            
        q = nxt[0]
        items = query("SELECT pill_id,quantity FROM queue_items WHERE queue_id=?", (q['id'],))
        
        # Atomically reserve the queue
        conn = get_conn()
        cur = conn.execute("UPDATE queues SET status='in_progress' WHERE id=? AND status='pending'", (q['id'],))
        conn.commit()
        
        if not cur.rowcount or cur.rowcount == 0:
            _logger.info('Failed to reserve queue %s (already taken), skipping', q['id'])
            return False
            
        # Prepare payloads for both nodes
        payload1 = {
            'queue_id': q['id'],
            'patient_id': q['patient_id'], 
            'target_room': q['target_room'],
            'items': [{'pill_id': it['pill_id'], 'quantity': it['quantity']} for it in items]
        }
        payload2 = {
            'queue_id': q['id'],
            'patient_id': q['patient_id'],
            'target_room': q['target_room']
        }
        
        # Dispatch to both nodes simultaneously 
        client.publish('disp/cmd/1', json.dumps(payload1), qos=1, retain=False)
        client.publish('disp/cmd/2', json.dumps(payload2), qos=1, retain=False)
        
        # Mark both nodes as busy
        _node_ready[1] = False
        _node_ready[2] = False
        
        _logger.info('Successfully dispatched queue %s to both nodes', q['id'])
        return True
        
    except Exception as e:
        _logger.exception('Failed to dispatch next queue: %s', e)
        return False


# Removed _publish_pending_for_node - using centralized _dispatch_next_queue instead


def on_message(client, userdata, msg):
    try:
        _logger.info('MQTT message received - Topic: %s, Payload: %s', msg.topic, msg.payload.decode())
        payload = json.loads(msg.payload.decode())
        topic = msg.topic
        # try to extract node id from topic suffix (disp/ack/{nodeId}, disp/evt/{nodeId}, disp/state/{nodeId})
        parts = topic.split('/')
        node_id = None
        _logger.info('Topic parts: %s', parts)
        if len(parts) >= 3:
            try:
                node_id = int(parts[-1])
                _logger.info('Extracted node_id: %s', node_id)
            except Exception as e:
                _logger.warning('Failed to parse node_id from topic %s: %s', topic, e)
                node_id = None
        else:
            _logger.warning('Topic %s does not have enough parts for node_id extraction', topic)

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
                # Both nodes work independently - record completion
                if node_id == 1:
                    execute("INSERT INTO events(queue_id, event, message) VALUES(?,?,?)", (qid, 'evt_done_node1', json.dumps(payload)))
                    if st in ('timeout', 'failed'):
                        _logger.warning('Node1 failed/timeout for queue %s: %s', qid, st)
                    else:
                        _logger.info('Node1 completed processing for queue %s', qid)
                elif node_id == 2:
                    execute("INSERT INTO events(queue_id, event, message) VALUES(?,?,?)", (qid, 'evt_done_node2', json.dumps(payload)))
                    if st in ('timeout', 'failed'):
                        _logger.warning('Node2 failed/timeout for queue %s: %s', qid, st)
                    else:
                        _logger.info('Node2 completed processing for queue %s', qid)
                
                # Check if both nodes completed this queue (success, failed, or timeout)
                node1_done = query("SELECT 1 FROM events WHERE queue_id=? AND event='evt_done_node1'", (qid,))
                node2_done = query("SELECT 1 FROM events WHERE queue_id=? AND event='evt_done_node2'", (qid,))
                
                if node1_done and node2_done:
                    # Both nodes completed - determine final status
                    # Get both statuses to decide final result
                    node1_status = query("SELECT message FROM events WHERE queue_id=? AND event='evt_done_node1' ORDER BY id DESC LIMIT 1", (qid,))
                    node2_status = query("SELECT message FROM events WHERE queue_id=? AND event='evt_done_node2' ORDER BY id DESC LIMIT 1", (qid,))
                    
                    try:
                        n1_msg = json.loads(node1_status[0]['message']) if node1_status else {}
                        n2_msg = json.loads(node2_status[0]['message']) if node2_status else {}
                        n1_st = n1_msg.get('status', 'unknown')
                        n2_st = n2_msg.get('status', 'unknown')
                    except:
                        n1_st = n2_st = 'unknown'
                    
                    # Final status logic: success only if both success, otherwise failed
                    if n1_st == 'success' and n2_st == 'success':
                        execute("UPDATE queues SET status=?, served_at=CURRENT_TIMESTAMP WHERE id=?", ('success', qid))
                        _logger.info('Queue %s completed successfully by both nodes', qid)
                    else:
                        # Failed case: timeout, failed, or mixed results
                        failure_reason = f"node1:{n1_st}, node2:{n2_st}"
                        _logger.warning('Queue %s FAILED - changing status to failed. Reason: %s', qid, failure_reason)
                        
                        # Update queue status to 'failed'
                        try:
                            execute("UPDATE queues SET status=? WHERE id=?", ('failed', qid))
                            execute("INSERT INTO events(queue_id, event, message) VALUES(?,?,?)", (qid, 'queue_failed', failure_reason))
                            _logger.info('Successfully updated queue %s status to FAILED', qid)
                        except Exception as e:
                            _logger.exception('Failed to update queue %s to failed status: %s', qid, e)
                    
                    # Mark both nodes as ready regardless of success/failure
                    _node_ready[1] = True
                    _node_ready[2] = True
                    _logger.info('Both nodes marked ready after queue %s completion', qid)
                    
                    # Try to dispatch next queue
                    _dispatch_next_queue(client)
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
                
                # Debug: show current ready states
                _logger.info('Current ready states - Node1: %s, Node2: %s', 
                           _node_ready.get(1, False), _node_ready.get(2, False))

                # Try to dispatch next queue if both nodes are ready
                _dispatch_next_queue(client)
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
        
        # Test publish to see if MQTT is working
        import time
        time.sleep(1)  # Wait for connection to stabilize
        c.publish('test/server', 'Server started', qos=1)
        _logger.info('Sent test message to test/server')
        
        return _client
    except Exception as e:
        _logger.warning('Could not connect to MQTT broker %s:%s — proceeding without MQTT (%s)', MQTT_BROKER, MQTT_PORT, e)
        _client = _DummyClient()
        return _client
