import cv2
import numpy as np
import time
import json
import argparse
import threading
try:
    import paho.mqtt.client as mqtt
except Exception:
    mqtt = None

# --- Configuration via CLI ---
parser = argparse.ArgumentParser(description='Camera-based pill count verifier (integrates with MQTT disp/cmd).')
parser.add_argument('--node-id', type=int, default=1, help='Node ID (matches MQTT topic suffix)')
parser.add_argument('--broker', type=str, default='127.0.0.1', help='MQTT broker host')
parser.add_argument('--port', type=int, default=1883, help='MQTT broker port')
parser.add_argument('--device', type=int, default=0, help='Camera device index')
parser.add_argument('--timeout', type=int, default=12, help='Max seconds to attempt detection')
parser.add_argument('--confirm-frames', type=int, default=4, help='Consecutive frames required to confirm detection')
parser.add_argument('--min-radius', type=int, default=8, help='Min circle radius')
parser.add_argument('--max-radius', type=int, default=80, help='Max circle radius')
parser.add_argument('--settle-delay', type=float, default=0.8, help='Seconds to wait for pills to settle before counting')
parser.add_argument('--window-size', type=int, default=8, help='Number of recent frames to consider for smoothing')
args = parser.parse_args()

NODE_ID = args.node_id
MQTT_BROKER = args.broker
MQTT_PORT = args.port
CAM_DEVICE = args.device
DETECT_TIMEOUT = args.timeout
CONFIRM_FRAMES = args.confirm_frames
MIN_RADIUS = args.min_radius
MAX_RADIUS = args.max_radius
SETTLE_DELAY = args.settle_delay
WINDOW_SIZE = args.window_size

TOPIC_CMD = f'disp/cmd/{NODE_ID}'
TOPIC_ACK = f'disp/ack/{NODE_ID}'
TOPIC_EVT = f'disp/evt/{NODE_ID}'
TOPIC_STATE = f'disp/state/{NODE_ID}'

_client = None


def _safe_print(*a, **k):
    try:
        print(*a, **k)
    except Exception:
        pass


def on_connect(client, userdata, flags, rc):
    _safe_print('MQTT connected, subscribing to', TOPIC_CMD)
    client.subscribe(TOPIC_CMD)
    # publish online/ready state
    try:
        client.publish(TOPIC_STATE, json.dumps({'online':1, 'ready':1}), qos=1)
    except Exception:
        pass


def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
    except Exception as e:
        _safe_print('Invalid payload on', msg.topic, e)
        return
    _safe_print('CMD received:', payload)
    # send immediate ack accepted
    ack = {'queue_id': payload.get('queue_id'), 'accepted': 1}
    try:
        client.publish(TOPIC_ACK, json.dumps(ack), qos=1)
    except Exception:
        _safe_print('Failed to publish ACK')

    # start detection in background thread
    t = threading.Thread(target=process_queue_detection, args=(payload,), daemon=True)
    t.start()


def publish_evt(qid, status, detected, expected, detail=None):
    msg = {'queue_id': qid, 'done': 1, 'status': status, 'detected': detected, 'expected': expected}
    if detail:
        msg['detail'] = str(detail)
    try:
        _client.publish(TOPIC_EVT, json.dumps(msg), qos=1)
        _safe_print('Published EVT:', msg)
    except Exception as e:
        _safe_print('Failed to publish EVT', e)


def detect_pills_from_camera(expected_count):
    # open camera
    cap = cv2.VideoCapture(CAM_DEVICE)
    # on windows, using CAP_DSHOW sometimes helps
    try:
        if not cap.isOpened():
            # try alternative backend
            cap = cv2.VideoCapture(CAM_DEVICE, cv2.CAP_DSHOW)
    except Exception:
        pass

    if not cap.isOpened():
        _safe_print('ไม่สามารถเปิดกล้องได้')
        return None

    start = time.time()
    consec = 0
    detected_best = 0
    counts_history = []
    first_detected = False

    # Settle delay: give pills time to fall/settle before counting
    settle_start = time.time()
    while time.time() - settle_start < SETTLE_DELAY:
        ret, frame = cap.read()
        if not ret:
            break
        cv2.putText(frame, f'Settling... {int((SETTLE_DELAY - (time.time()-settle_start))*1000)/1000}s', (10,30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,128,255),2)
        cv2.imshow('Camera Verify', frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            cap.release()
            try:
                cv2.destroyAllWindows()
            except Exception:
                pass
            return None

    while True:
        ret, frame = cap.read()
        if not ret:
            _safe_print('ไม่สามารถอ่านภาพได้')
            break

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (7,7), 1.5)

        circles = cv2.HoughCircles(
            gray,
            cv2.HOUGH_GRADIENT,
            dp=1.2,
            minDist=20,
            param1=100,
            param2=28,
            minRadius=MIN_RADIUS,
            maxRadius=MAX_RADIUS
        )

        count = 0
        if circles is not None:
            circles = np.uint16(np.around(circles))
            count = len(circles[0])
            # draw for debug
            for (x, y, r) in circles[0, :]:
                cv2.circle(frame, (x, y), r, (0, 255, 0), 2)
                cv2.circle(frame, (x, y), 2, (0, 0, 255), 3)

        counts_history.append(count)
        if len(counts_history) > 30:
            counts_history.pop(0)

        # smoothing: pick the max in recent window (WINDOW_SIZE)
        recent_max = max(counts_history[-WINDOW_SIZE:]) if counts_history else 0
        detected_best = max(detected_best, recent_max)

        # check consecutive confirmation: if recent_max >= expected_count for CONFIRM_FRAMES frames
        if expected_count is not None and recent_max >= expected_count:
            consec += 1
        else:
            consec = 0

        # show overlay for debugging (optional)
        cv2.putText(frame, f'Detected: {recent_max} / Expected: {expected_count}', (10,30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,0,0),2)
        cv2.imshow('Camera Verify', frame)

        # Confirm success
        if expected_count is not None and consec >= CONFIRM_FRAMES:
            cap.release()
            cv2.destroyWindow('Camera Verify')
            return detected_best

        # timeout
        if time.time() - start > DETECT_TIMEOUT:
            cap.release()
            try:
                cv2.destroyWindow('Camera Verify')
            except Exception:
                pass
            return detected_best

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    try:
        cv2.destroyAllWindows()
    except Exception:
        pass
    return detected_best


def process_queue_detection(payload):
    qid = payload.get('queue_id')
    items = payload.get('items') or []
    expected = 0
    try:
        # Sum quantities across all items (adjust if you need per-pill checks)
        expected = sum(int(it.get('quantity', 0)) for it in items)
    except Exception:
        expected = None

    _safe_print(f'Starting detection for queue {qid} expecting {expected} pills')
    detected = detect_pills_from_camera(expected)
    if detected is None:
        publish_evt(qid, 'failed', 0, expected, detail='camera_error')
        return

    status = 'success' if (expected is not None and detected >= expected) else 'failed'
    detail = f'detected={detected}'
    publish_evt(qid, status, detected, expected, detail=detail)


def main():
    global _client
    if mqtt is None:
        _safe_print('paho-mqtt not installed, MQTT functionality disabled')
        return

    _client = mqtt.Client()
    _client.on_connect = on_connect
    _client.on_message = on_message
    try:
        _client.connect(MQTT_BROKER, MQTT_PORT, 60)
        _client.loop_start()
    except Exception as e:
        _safe_print('Could not connect to MQTT broker', e)
        return

    _safe_print('Camera verifier running. Waiting for disp/cmd/...')
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        _safe_print('Shutting down')
    finally:
        try:
            _client.publish(TOPIC_STATE, json.dumps({'online':0, 'ready':0}), qos=1)
        except Exception:
            pass
        try:
            _client.loop_stop()
            _client.disconnect()
        except Exception:
            pass


if __name__ == '__main__':
    main()
