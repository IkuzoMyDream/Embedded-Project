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
    global _client
    """Atomically update SQLite DB when a node finishes a queue"""
    conn = get_conn()
    try:
        # Use transaction to ensure atomicity
        conn.execute("BEGIN IMMEDIATE")  # Lock database immediately
        
        # Insert event row "evt_done_node{node_id}" with payload JSON
        event_name = f'evt_done_node{node_id}'
        
        # Check if this node already completed this queue (prevent duplicates)
        existing = conn.execute("SELECT 1 FROM events WHERE queue_id=? AND event=?", (qid, event_name)).fetchone()
        if existing:
            _logger.warning('Node%s already completed queue %s, ignoring duplicate', node_id, qid)
            conn.rollback()
            return
        
        # Record this node's completion event
        cur_evt = conn.execute("INSERT INTO events(queue_id, event, message) VALUES(?,?,?)", 
                    (qid, event_name, json.dumps(payload)))
        inserted_evt_id = cur_evt.lastrowid

        # Server-side verification: if payload includes 'detected', compare with DB expected total
        try:
            detected = None
            if isinstance(payload, dict):
                detected = payload.get('detected')
            if detected is not None:
                # get expected total from queue_items
                row = conn.execute("SELECT SUM(quantity) as total FROM queue_items WHERE queue_id=?", (qid,)).fetchone()
                expected_db = row[0] if row and row[0] is not None else 0
                try:
                    det_int = int(detected)
                except Exception:
                    det_int = None

                if det_int is None or det_int < int(expected_db):
                    _logger.warning('Server-side verification FAILED for queue %s node%s: detected=%s expected_db=%s', qid, node_id, detected, expected_db)
                    # update the inserted evt message to reflect failed status so later aggregation sees it
                    try:
                        mod = dict(payload)
                        mod['status'] = 'failed'
                        mod['verification'] = {'expected_db': expected_db, 'detected': detected}
                        conn.execute("UPDATE events SET message=? WHERE id=?", (json.dumps(mod), inserted_evt_id))
                        # also insert separate verification event for audit
                        conn.execute("INSERT INTO events(queue_id, event, message) VALUES(?,?,?)", (qid, 'node_verification_failed', json.dumps({'node': node_id, 'detected': detected, 'expected_db': expected_db})))
                        # reflect failure in local status variable so logs show fail
                        status = 'failed'
                        # Immediately mark queue as failed in DB and record reason
                        reason = f'verification_failed_node{node_id}:detected={detected}:expected={expected_db}'
                        conn.execute("UPDATE queues SET status=?, failed_reason=? WHERE id=?", ('failed', reason, qid))
                        conn.execute("INSERT INTO events(queue_id, event, message) VALUES(?,?,?)", (qid, 'queue_failed', reason))
                        # commit now so queue state is persisted and we can dispatch next
                        conn.commit()
                        # mark node ready and attempt dispatch next
                        _node_ready[node_id] = True
                        if _client:
                            try:
                                _logger.info('Triggering dispatch after verification-failed for queue %s', qid)
                                _dispatch_next_queue(_client)
                            except Exception as e:
                                _logger.exception('Failed to trigger dispatch after verification failed: %s', e)
                        # return early - this queue is failed and no need to wait for other node
                        return
                    except Exception as e:
                        _logger.exception('Failed to update event after verification: %s', e)
                else:
                    # verification passed - add audit event
                    conn.execute("INSERT INTO events(queue_id, event, message) VALUES(?,?,?)", (qid, 'node_verification_pass', json.dumps({'node': node_id, 'detected': detected, 'expected_db': expected_db})))
        except Exception as e:
            _logger.exception('Server-side verification error: %s', e)

        # Log completion
        if status in ('timeout', 'failed'):
            _logger.warning('Node%s failed/timeout for queue %s: %s', node_id, qid, status)
        else:
            _logger.info('Node%s completed processing for queue %s', node_id, qid)
        
        # Check if both node1 and node2 have done this queue (within this transaction)
        node1_done = conn.execute("SELECT 1 FROM events WHERE queue_id=? AND event='evt_done_node1'", (qid,)).fetchone()
        node2_done = conn.execute("SELECT 1 FROM events WHERE queue_id=? AND event='evt_done_node2'", (qid,)).fetchone()
        
        if node1_done and node2_done:
            # Both nodes completed - get their statuses
            node1_result = conn.execute("SELECT message FROM events WHERE queue_id=? AND event='evt_done_node1' ORDER BY id DESC LIMIT 1", (qid,)).fetchone()
            node2_result = conn.execute("SELECT message FROM events WHERE queue_id=? AND event='evt_done_node2' ORDER BY id DESC LIMIT 1", (qid,)).fetchone()
            
            try:
                n1_msg = json.loads(node1_result[0]) if node1_result else {}
                n2_msg = json.loads(node2_result[0]) if node2_result else {}
                n1_st = n1_msg.get('status', 'success').lower()
                n2_st = n2_msg.get('status', 'success').lower()
            except Exception as e:
                _logger.exception('Failed to parse node completion status: %s', e)
                n1_st = n2_st = 'failed'  # Mark as failed on parse error
            
            # If both success: update queues.status='success' + served_at=NOW
            # If one failed or timeout: update queues.status='failed'
            if n1_st == 'success' and n2_st == 'success':
                conn.execute("UPDATE queues SET status=?, served_at=CURRENT_TIMESTAMP WHERE id=?", ('success', qid))
                _logger.info('Queue %s completed successfully by both nodes', qid)
            else:
                # Failed case: timeout, failed, or mixed results
                failure_reason = f"node1:{n1_st}, node2:{n2_st}"
                _logger.warning('Queue %s FAILED - changing status to failed. Reason: %s', qid, failure_reason)
                conn.execute("UPDATE queues SET status=? WHERE id=?", ('failed', qid))
                conn.execute("INSERT INTO events(queue_id, event, message) VALUES(?,?,?)", (qid, 'queue_failed', failure_reason))
        
        # Commit transaction
        conn.commit()
        
        # After commit: mark in-memory _node_ready[node_id] = True
        _node_ready[node_id] = True
        _logger.info('Node%s marked ready after completing queue %s', node_id, qid)
        
        # 3. When both nodes send evt_done (success):
        # -> update queue.status = 'success', served_at=NOW (done above)
        # -> mark _node_ready[1] = True, _node_ready[2] = True (done above)
        # -> trigger _dispatch_next_queue again
        if node1_done and node2_done and _check_both_nodes_ready():
            if _client:
                _logger.info('Both nodes completed queue %s - triggering next dispatch', qid)
                _dispatch_next_queue(_client)
            
    except Exception as e:
        conn.rollback()
        _logger.exception('Failed to handle node completion atomically: %s', e)
    finally:
        conn.close()


def _dispatch_next_queue(client):
    """Dispatcher for MQTT-based queue system with strict FIFO and single in_progress rule"""
    try:
        _logger.info('_dispatch_next_queue called - scanning DB directly')
        
        # Always scan the queues table directly (not just memory flags)
        # Rule: at most 1 queue can be in_progress at a time
        # Priority order is strict FIFO (lowest queue.id first)
        
        # 1. If there is any queue with status='in_progress':
        in_progress_queues = query("SELECT id, patient_id, target_room FROM queues WHERE status='in_progress' ORDER BY id ASC")
        
        if in_progress_queues:
            # -> select the lowest-id in_progress queue
            # -> monitor it until done (no new dispatch until it finishes)
            active_queue = in_progress_queues[0]
            _logger.info('Monitoring in_progress queue %s - no new dispatch until it finishes', active_queue['id'])
            
            # If there are multiple in_progress (should not happen but handle gracefully)
            if len(in_progress_queues) > 1:
                extra_ids = [str(q['id']) for q in in_progress_queues[1:]]
                _logger.warning('Found multiple in_progress queues (should not happen): monitoring %s, extras: %s', 
                               active_queue['id'], ', '.join(extra_ids))
            
            return False  # No new dispatch while monitoring
        
        # 2. If there are no in_progress queues:
        # -> select the lowest-id pending queue (status='pending')
        pending_queues = query("SELECT id, patient_id, target_room FROM queues WHERE status='pending' ORDER BY id ASC LIMIT 1")
        
        if not pending_queues:
            _logger.info('No pending queues to dispatch')
            return False
        
        # Check if both nodes are ready before attempting dispatch
        if not _check_both_nodes_ready():
            _logger.info('Dispatch skipped - Nodes not both ready - Node1: %s, Node2: %s', 
                         _node_ready.get(1, False), _node_ready.get(2, False))
            return False
            
        q = pending_queues[0]
        items = query("SELECT pill_id,quantity FROM queue_items WHERE queue_id=?", (q['id'],))
        
        # -> atomically UPDATE that queue to 'in_progress'
        conn = get_conn()
        try:
            # Handle transactions with BEGIN IMMEDIATE to prevent race
            conn.execute("BEGIN IMMEDIATE")
            
            # Atomic check: ensure no other in_progress exists and this queue is still pending
            cur = conn.execute("""
                UPDATE queues SET status='in_progress' 
                WHERE id=? AND status='pending' 
                AND NOT EXISTS (SELECT 1 FROM queues WHERE status='in_progress')
            """, (q['id'],))
            
            if not cur.rowcount or cur.rowcount == 0:
                _logger.warning('Failed to atomically reserve queue %s (already taken or another queue became in_progress)', q['id'])
                conn.rollback()
                return False
                
            conn.commit()
            _logger.info('Successfully reserved queue %s for dispatch (FIFO strict)', q['id'])
            
        except Exception as e:
            conn.rollback()
            _logger.exception('Failed to reserve queue %s atomically: %s', q['id'], e)
            return False
        finally:
            conn.close()
            
        # -> publish MQTT messages:
        # - disp/cmd/1 (with full items)
        # - disp/cmd/2 (with trigger only)
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
        
        # Publish to both nodes simultaneously 
        client.publish('disp/cmd/1', json.dumps(payload1), qos=1, retain=False)
        client.publish('disp/cmd/2', json.dumps(payload2), qos=1, retain=False)
        
        # -> mark _node_ready[1] = False, _node_ready[2] = False
        _node_ready[1] = False
        _node_ready[2] = False
        
        _logger.info('Successfully dispatched queue %s to both nodes (FIFO: lowest id first)', q['id'])
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
