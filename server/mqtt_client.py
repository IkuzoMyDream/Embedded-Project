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


def _handle_node_completion_atomic(qid, node_id, status, payload):
    """Handle node completion atomically to prevent race conditions"""
    conn = get_conn()
    try:
        # Use transaction to ensure atomicity
        conn.execute("BEGIN IMMEDIATE")  # Lock database immediately
        
        # Check if this node already completed this queue (prevent duplicates)
        event_name = f'evt_done_node{node_id}'
        existing = conn.execute("SELECT 1 FROM events WHERE queue_id=? AND event=?", (qid, event_name)).fetchone()
        if existing:
            _logger.warning('Node%s already completed queue %s, ignoring duplicate', node_id, qid)
            conn.rollback()
            return
        
        # Record this node's completion event
        conn.execute("INSERT INTO events(queue_id, event, message) VALUES(?,?,?)", 
                    (qid, event_name, json.dumps(payload)))
        
        # Log completion
        if status in ('timeout', 'failed'):
            _logger.warning('Node%s failed/timeout for queue %s: %s', node_id, qid, status)
        else:
            _logger.info('Node%s completed processing for queue %s', node_id, qid)
        
        # Check if both nodes have completed (within this transaction)
        node1_done = conn.execute("SELECT 1 FROM events WHERE queue_id=? AND event='evt_done_node1'", (qid,)).fetchone()
        node2_done = conn.execute("SELECT 1 FROM events WHERE queue_id=? AND event='evt_done_node2'", (qid,)).fetchone()
        
        if node1_done and node2_done:
            # Both nodes completed - get their statuses
            node1_result = conn.execute("SELECT message FROM events WHERE queue_id=? AND event='evt_done_node1' ORDER BY id DESC LIMIT 1", (qid,)).fetchone()
            node2_result = conn.execute("SELECT message FROM events WHERE queue_id=? AND event='evt_done_node2' ORDER BY id DESC LIMIT 1", (qid,)).fetchone()
            
            try:
                n1_msg = json.loads(node1_result[0]) if node1_result else {}
                n2_msg = json.loads(node2_result[0]) if node2_result else {}
                n1_st = n1_msg.get('status', 'success').lower()  # Default to success instead of unknown
                n2_st = n2_msg.get('status', 'success').lower()  # Default to success instead of unknown
            except Exception as e:
                _logger.exception('Failed to parse node completion status: %s', e)
                n1_st = n2_st = 'failed'  # Mark as failed on parse error
            
            # Determine final status - success only if both success
            if n1_st == 'success' and n2_st == 'success':
                conn.execute("UPDATE queues SET status=?, served_at=CURRENT_TIMESTAMP WHERE id=?", ('success', qid))
                _logger.info('Queue %s completed successfully by both nodes', qid)
            else:
                # Failed case: timeout, failed, or mixed results
                failure_reason = f"node1:{n1_st}, node2:{n2_st}"
                _logger.warning('Queue %s FAILED - changing status to failed. Reason: %s', qid, failure_reason)
                conn.execute("UPDATE queues SET status=? WHERE id=?", ('failed', qid))
                conn.execute("INSERT INTO events(queue_id, event, message) VALUES(?,?,?)", (qid, 'queue_failed', failure_reason))
            
            # Mark both nodes as ready for next queue
            _node_ready[1] = True
            _node_ready[2] = True
            _logger.info('Both nodes marked ready after queue %s completion', qid)
        
        # Commit transaction
        conn.commit()
        
        # Try to dispatch next queue if both nodes are ready (outside transaction)
        if node1_done and node2_done and _check_both_nodes_ready():
            # Get global client reference
            global _client
            if _client:
                _dispatch_next_queue(_client)
            
    except Exception as e:
        conn.rollback()
        _logger.exception('Failed to handle node completion atomically: %s', e)
    finally:
        conn.close()


def _dispatch_next_queue(client):
    """Dispatch next pending queue to both nodes simultaneously (FIFO strict)"""
    try:
        _logger.info('_dispatch_next_queue called')
        
        # Check if both nodes are ready
        if not _check_both_nodes_ready():
            _logger.info('Dispatch skipped - Nodes not both ready - Node1: %s, Node2: %s', 
                         _node_ready.get(1, False), _node_ready.get(2, False))
            return False
        
        # CRITICAL FIX: Check if there's already an active queue in_progress
        active_queues = query("SELECT id FROM queues WHERE status='in_progress'")
        if active_queues:
            active_ids = [str(q['id']) for q in active_queues]
            _logger.info('Dispatch skipped - Already have active queue(s) in_progress: %s', ', '.join(active_ids))
            return False
            
        # Get next pending queue (FIFO strict)
        nxt = query("SELECT id, patient_id, target_room FROM queues WHERE status='pending' ORDER BY id ASC LIMIT 1")
        if not nxt:
            _logger.info('No pending queue to dispatch')
            return False
            
        q = nxt[0]
        items = query("SELECT pill_id,quantity FROM queue_items WHERE queue_id=?", (q['id'],))
        
        # Atomically reserve the queue with additional safety check
        conn = get_conn()
        
        # Double check: ensure no other in_progress exists and this queue is still pending
        cur = conn.execute("""
            UPDATE queues SET status='in_progress' 
            WHERE id=? AND status='pending' 
            AND NOT EXISTS (SELECT 1 FROM queues WHERE status='in_progress' AND id != ?)
        """, (q['id'], q['id']))
        conn.commit()
        
        if not cur.rowcount or cur.rowcount == 0:
            _logger.warning('Failed to reserve queue %s (already taken or active queue exists)', q['id'])
            conn.close()
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


# centralized _dispatch_next_queue


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
                # Use atomic transaction to prevent race conditions
                _handle_node_completion_atomic(qid, node_id, st, payload)
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

                # NOTE: Don't auto-dispatch here to prevent multiple in_progress queues
                # Dispatch only happens after both nodes complete a queue
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
        
        # Initial dispatch attempt after server starts (if nodes become ready)
        def delayed_initial_dispatch():
            time.sleep(3)  # Wait for nodes to connect and report ready
            try:
                _dispatch_next_queue(c)
            except Exception as e:
                _logger.warning('Initial dispatch failed: %s', e)
        
        import threading
        threading.Thread(target=delayed_initial_dispatch, daemon=True).start()
        
        return _client
    except Exception as e:
        _logger.warning('Could not connect to MQTT broker %s:%s — proceeding without MQTT (%s)', MQTT_BROKER, MQTT_PORT, e)
        _client = _DummyClient()
        return _client
