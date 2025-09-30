import cv2
import numpy as np
import time
import threading
import requests
import paho.mqtt.client as mqtt
import os
import collections
import statistics
import json

# Backend / MQTT configuration
API_BASE = os.environ.get('DISPENSE_API_BASE', 'http://localhost:5000')
VISION_MQTT_BROKER = os.environ.get('VISION_MQTT_BROKER', '127.0.0.1')
VISION_MQTT_PORT = int(os.environ.get('VISION_MQTT_PORT', '1883'))
VISION_CMD_TOPIC = os.environ.get('VISION_CMD_TOPIC', 'disp/cmd/2')  # subscribe to node 2 commands
VISION_EVT_TOPIC = os.environ.get('VISION_EVT_TOPIC', 'disp/evt/2')  # publish events to node 2

POST_INTERVAL_SEC = float(os.environ.get('VISION_POST_INTERVAL', '2.0'))  # (legacy) ยังเหลือไว้แต่ไม่ได้ใช้ส่งแล้ว

# การตั้งค่าการทำให้ค่าคงที่ (stabilization)
STABILIZE_WINDOW = int(os.environ.get('VISION_STABILIZE_WINDOW', '7'))  # จำนวนเฟรมย้อนหลัง
STABLE_METHOD = os.environ.get('VISION_STABLE_METHOD', 'mode')  # mode | median | mean

# พักหลังนับครบ (คงที่เท่ากับ expected) เพื่อไม่สแปม (วินาที)
PAUSE_AFTER_MATCH = float(os.environ.get('VISION_PAUSE_AFTER_MATCH', '15.0'))

# หาก stable count เดิมซ้ำ และเพิ่งส่งไป ไม่ต้องส่งอีกในช่วง Quiet TTL
QUIET_SAMPLE_TTL = float(os.environ.get('VISION_QUIET_SAMPLE_TTL', '20.0'))

# ตรวจคิวใหม่ทุก ๆ n วินาที
QUEUE_POLL_INTERVAL = float(os.environ.get('VISION_QUEUE_POLL_INTERVAL', '3.0'))

last_post_at = 0.0                 # legacy
latest_frame_count = 0             # ค่าจำนวนล่าสุดจากเฟรมดิบ
stable_count = None                # ค่าหลังทำให้คงที่ (mode/median/mean)
last_stable_sent = None            # legacy (ใช้เป็น fallback)
stable_buffer = collections.deque(maxlen=STABILIZE_WINDOW)
lock = threading.Lock()
peak_count = 0  # ค่าสูงสุดที่เคยตรวจพบในคิวปัจจุบัน (peak / maximum)
cumulative_count = 0  # จำนวนนับสะสม (สำหรับโหมดเม็ดยาลงมาเป็นช่วง ๆ)
LAST_FRAME_CENTROIDS = []  # centroids เฟรมก่อนหน้า (สำหรับ matching คร่าว ๆ)

# โหมดการนับ: peak | cumulative | single (ผ่าน ENV)
VISION_COUNT_MODE = os.environ.get('VISION_COUNT_MODE', 'peak').lower()
SINGLE_DEBOUNCE_SEC = float(os.environ.get('VISION_SINGLE_DEBOUNCE', '0.35'))  # กัน detect ซ้ำในโหมด single
SINGLE_MIN_HOLD_FRAMES = int(os.environ.get('VISION_SINGLE_MIN_HOLD', '1'))    # ต้องเห็น >= N เฟรมก่อนนับ (ลด noise)
single_last_seen_at = 0.0
single_present_frames = 0
single_total = 0  # ผลรวมในโหมด single
# พารามิเตอร์สำหรับ cumulative mode
TRACK_DIST_THRESHOLD = float(os.environ.get('VISION_TRACK_DIST_THRESHOLD', '45'))  # ระยะ px ถือว่าวัตถุเดิม
ENTRANCE_LINE_Y = int(os.environ.get('VISION_ENTRANCE_LINE_Y', '200'))  # เส้นสมมุติที่เม็ดยาผ่านแล้วถือว่าใหม่
REENTRY_COOLDOWN_SEC = float(os.environ.get('VISION_REENTRY_COOLDOWN', '1.2'))  # กันไม่นับซ้ำเร็วเกิน
recent_entries = []  # list ของ (timestamp, (cx,cy)) สำหรับกันนับซ้ำ
last_increment_at = 0.0  # เวลาเฟรมล่าสุดที่นับเพิ่ม
last_increment_amount = 0  # จำนวนที่เพิ่มครั้งล่าสุด (ปกติ = จำนวน new_objects)

# ข้อมูลคิวปัจจุบันที่กำลัง dispense (รับจาก MQTT cmd)
current_queue_id = None
current_queue_number = None
expected_total = None
last_queue_poll = 0.0
paused_until = 0.0
mqtt_client = None  # MQTT client instance
pill_status = "unknown"  # ยาครบ, ยาไม่ครบ, unknown (ใช้เฉพาะรับ vision_complete จากระบบอื่น)
final_sent_for = None  # queue_id ล่าสุดที่ส่ง vision_complete แล้ว
FINAL_DELAY_SEC = float(os.environ.get('VISION_FINAL_DELAY', '0.5'))  # หน่วงหลัง evt success จาก node2

def on_mqtt_connect(client, userdata, flags, rc):
    print(f"[vision] MQTT connected with result code {rc}")
    if rc == 0:
        # Subscribe to command topic for node 2
        client.subscribe(VISION_CMD_TOPIC)
        print(f"[vision] subscribed to {VISION_CMD_TOPIC}")
        # Subscribe to event topic for node 2 to listen for pill status
        client.subscribe(VISION_EVT_TOPIC)
        print(f"[vision] subscribed to {VISION_EVT_TOPIC} for pill status updates")

def publish_final_vision():
    """ส่งผล vision ครั้งเดียวตอน node2 success (finalize-on-trigger mode)"""
    global final_sent_for, last_stable_sent
    if current_queue_id is None:
        return
    if final_sent_for == current_queue_id:
        return
    with lock:
        if VISION_COUNT_MODE == 'cumulative':
            final = int(cumulative_count)
        elif VISION_COUNT_MODE == 'single':
            final = int(single_total)
        else:
            final = int(peak_count)
    evt_payload = {
        "queue_id": current_queue_id,
        "done": 1,
        "status": "vision_complete",
        "count_detected": final,
        "expected": expected_total
    }
    try:
        if mqtt_client and mqtt_client.is_connected():
            mqtt_client.publish(VISION_EVT_TOPIC, json.dumps(evt_payload), qos=1)
            print(f"[vision] vision_complete published {final}/{expected_total} queue={current_queue_id}")
        else:
            # fallback HTTP (optional)
            try:
                r = requests.post(f"{API_BASE}/api/vision/current", json={"count_detected": final}, timeout=2.0)
                print(f"[vision] HTTP finalize status={r.status_code}")
            except Exception as e:
                print(f"[vision] HTTP finalize failed: {e}")
    finally:
        final_sent_for = current_queue_id


def on_mqtt_message(client, userdata, msg):
    global current_queue_id, current_queue_number, expected_total, pill_status, final_sent_for, peak_count, cumulative_count, LAST_FRAME_CENTROIDS, recent_entries, last_increment_at, last_increment_amount, single_last_seen_at, single_present_frames, single_total
    try:
        payload = json.loads(msg.payload.decode())
        print(f"[vision] received message on {msg.topic}: {payload}")
        
        # Handle command messages (from server to start vision for a queue)
        if msg.topic == VISION_CMD_TOPIC:
            # New or repeated queue command -> reset finalize state so we can resend even if queue_id reused
            qid_new = payload.get('queue_id')
            if qid_new != current_queue_id or final_sent_for == qid_new:
                # reset counters / buffers
                with lock:
                    stable_buffer.clear()
                    peak_count = 0
                    cumulative_count = 0
                    LAST_FRAME_CENTROIDS = []
                    recent_entries.clear()
                    last_increment_at = 0.0
                    last_increment_amount = 0
                    single_last_seen_at = 0.0
                    single_present_frames = 0
                    single_total = 0
                print(f"[vision] reset state for queue {qid_new} (previous final_sent_for={final_sent_for})")
                # reset state variables
                final_sent_for = None
                last_stable_sent = None
                stable_count = None
                paused_until = 0.0
                pill_status = "unknown"
            # Extract queue info
            current_queue_id = qid_new
            current_queue_number = payload.get('queue_number') or str(current_queue_id)
            # Calculate expected total
            items = payload.get('items', [])
            exp = 0
            for it in items:
                try:
                    exp += int(it.get('quantity', 0))
                except:
                    pass
            expected_total = exp if exp > 0 else None
            print(f"[vision] new queue #{current_queue_number} (id={current_queue_id}) expected={expected_total}")
            
        # Handle event messages (vision results from other processes)
        elif msg.topic == VISION_EVT_TOPIC:
            # ถ้าเป็น success จาก node2 (จ่ายเสร็จ) ให้ trigger ส่งผล vision ครั้งเดียว
            st = (payload.get('status') or '').lower()
            if payload.get('done') == 1 and st == 'success':
                qid = payload.get('queue_id')
                if qid == current_queue_id:
                    if final_sent_for == qid:
                        print(f"[vision] final already sent for queue {qid}, skip")
                    else:
                        print(f"[vision] node2 success -> schedule final vision in {FINAL_DELAY_SEC}s (queue {qid})")
                        threading.Timer(FINAL_DELAY_SEC, publish_final_vision).start()
            elif st == 'vision_complete':
                # vision_complete ที่มาจากระบบอื่น (หรือ echo) ใช้แค่ update สถานะในจอ (ถ้าต้อง)
                count_detected = payload.get('count_detected')
                expected = payload.get('expected')
                if count_detected is not None and expected is not None:
                    pill_status = "ยาครบ" if count_detected == expected else "ยาไม่ครบ"
                    print(f"[vision] external vision_complete {count_detected}/{expected} -> {pill_status}")
                else:
                    pill_status = "unknown"
                    print("[vision] external vision_complete missing counts")
        
    except Exception as e:
        print(f"[vision] failed to parse MQTT message: {e}")

def setup_mqtt():
    global mqtt_client
    try:
        mqtt_client = mqtt.Client()
        mqtt_client.on_connect = on_mqtt_connect
        mqtt_client.on_message = on_mqtt_message
        mqtt_client.connect(VISION_MQTT_BROKER, VISION_MQTT_PORT, keepalive=60)
        mqtt_client.loop_start()
        print(f"[vision] MQTT setup complete - broker {VISION_MQTT_BROKER}:{VISION_MQTT_PORT}")
        return True
    except Exception as e:
        print(f"[vision] MQTT setup failed: {e}")
        return False

def fetch_current_queue():
    global current_queue_id, expected_total, last_queue_poll, current_queue_number
    # ตอนนี้ข้อมูลคิวมาจาก MQTT แล้ว ไม่ต้อง poll HTTP dashboard
    # ยังคงไว้เป็น fallback สำหรับกรณี MQTT ไม่พร้อม
    if mqtt_client and mqtt_client.is_connected():
        last_queue_poll = time.time()
        return
        
    # Fallback to HTTP polling if MQTT not available
    try:
        r = requests.get(f"{API_BASE}/api/dashboard", timeout=1.5)
        if r.status_code != 200:
            return
        d = r.json()
        cq = d.get('current')
        if cq and cq.get('status') in ('in_progress', 'processing'):
            qid = cq.get('queue_id') or cq.get('id')
            qnum = cq.get('queue_number')
            items = cq.get('items') or []
            exp = 0
            for it in items:
                try:
                    exp += int(it.get('quantity') or 0)
                except:
                    pass
            if qid != current_queue_id:
                print(f"[vision] new active queue #{qnum} (id={qid}) expected={exp}")
            current_queue_id = qid
            current_queue_number = qnum
            expected_total = exp if exp > 0 else None
        else:
            if current_queue_id is not None:
                print("[vision] no active queue -> idle")
            current_queue_id = None
            current_queue_number = None
            expected_total = None
    except Exception:
        pass
    finally:
        last_queue_poll = time.time()

def compute_stable():
    global stable_count
    with lock:
        buf = list(stable_buffer)
    if not buf:
        stable_count = None
        return
    try:
        if STABLE_METHOD == 'median':
            stable_count = int(statistics.median(buf))
        elif STABLE_METHOD == 'mean':
            stable_count = int(round(sum(buf)/len(buf)))
        else:
            stable_count = int(statistics.mode(buf))
    except statistics.StatisticsError:
        stable_count = int(statistics.median(buf))

def should_post(now: float) -> bool:
    # legacy – ไม่ส่ง periodic แล้ว คืน False ตลอด
    return False

def poster_loop():
    # ปรับเหลือเฉพาะหน้าที่สร้าง stable_count ให้พร้อมตอน finalize เท่านั้น
    global paused_until
    while True:
        time.sleep(0.25)
        now = time.time()
        if now - last_queue_poll > QUEUE_POLL_INTERVAL:
            fetch_current_queue()
        compute_stable()
        if current_queue_id and expected_total is not None and stable_count is not None:
            if stable_count == expected_total and now >= paused_until:
                paused_until = now + PAUSE_AFTER_MATCH
                # แค่ log ไม่ส่งใด ๆ
                print(f"[vision] stable matches expected ({expected_total}) – waiting for node2 success evt")

threading.Thread(target=poster_loop, daemon=True).start()

# Setup MQTT connection to receive commands and send events
mqtt_setup_success = setup_mqtt()
if not mqtt_setup_success:
    print("[vision] Warning: MQTT not available, using HTTP fallback mode")

print(f"[vision] count mode = {VISION_COUNT_MODE} (set ENV VISION_COUNT_MODE=peak|cumulative|single)")

# เปิดกล้อง (CAM_INDEX override ผ่าน ENV ได้)
CAM_INDEX = int(os.environ.get('VISION_CAM_INDEX', '0'))
cap = cv2.VideoCapture(CAM_INDEX)

if not cap.isOpened():
    print("ไม่สามารถเปิดกล้องได้")
    exit()

while True:
    ret, frame = cap.read()
    if not ret:
        print("ไม่สามารถอ่านภาพได้")
        break

    # แปลงภาพเป็น grayscale
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # blur เพื่อลด noise
    gray = cv2.medianBlur(gray, 5)

    # หา circle ด้วย Hough Transform
    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=1,          # อัตราส่วนการลดขนาด
        minDist=50,    # ระยะห่างขั้นต่ำระหว่างวงกลม
        param1=100,    # Canny edge high threshold
        param2=30,     # ค่าความเข้มงวดของการตรวจจับ
        minRadius=10,  # รัศมีเล็กสุด
        maxRadius=200  # รัศมีใหญ่สุด
    )

    circle_count = 0
    if circles is not None:
        circles = np.uint16(np.around(circles))
        circle_count = circles.shape[1]   # จำนวนวงกลมที่เจอ
        for (x, y, r) in circles[0, :]:
            # วาดวงกลม
            cv2.circle(frame, (x, y), r, (0, 255, 0), 2)
            # วาดจุดศูนย์กลาง
            cv2.circle(frame, (x, y), 2, (0, 0, 255), 3)

    # เก็บลง buffer เพื่อทำให้ค่าคงที่ภายหลัง
    with lock:
        latest_frame_count = circle_count
        stable_buffer.append(circle_count)
        if VISION_COUNT_MODE == 'peak':
            if circle_count > peak_count:
                peak_count = circle_count
        elif VISION_COUNT_MODE == 'cumulative':
            centroids = []
            if circles is not None:
                for (x, y, r) in circles[0, :]:
                    centroids.append((int(x), int(y)))

            now_ts = time.time()
            # ล้าง recent_entries ที่หมดอายุ
            recent_entries[:] = [(t, c) for (t, c) in recent_entries if now_ts - t < REENTRY_COOLDOWN_SEC]

            # logic: ถ้า centroid ใหม่ (ไม่มีในเฟรมก่อน) และ ข้ามเส้น ENTRANCE_LINE_Y (y > line) -> นับเพิ่ม
            # วิธีง่าย ๆ: วัตถุถือว่า "ใหม่" ถ้าไม่มี centroid ใดใน LAST_FRAME_CENTROIDS อยู่ใกล้กว่า threshold
            new_objects = []
            for (cx, cy) in centroids:
                # ข้ามการนับถ้ายังไม่ผ่านเส้น
                if cy < ENTRANCE_LINE_Y:
                    continue
                # ตรวจว่าเพิ่งนับไปไม่นาน (กันเด้งซ้ำถ้ากลับขึ้นเล็กน้อย)
                skip_recent = False
                for (t_prev, (rx, ry)) in recent_entries:
                    if (cx - rx)**2 + (cy - ry)**2 <= (TRACK_DIST_THRESHOLD**2):
                        skip_recent = True
                        break
                if skip_recent:
                    continue
                matched_prev = False
                for (px, py) in LAST_FRAME_CENTROIDS:
                    if (cx - px)**2 + (cy - py)**2 <= (TRACK_DIST_THRESHOLD**2):
                        matched_prev = True
                        break
                if not matched_prev:
                    new_objects.append((cx, cy))

            for obj in new_objects:
                cumulative_count += 1
                recent_entries.append((now_ts, obj))
            if new_objects:
                last_increment_at = now_ts
                last_increment_amount = len(new_objects)
            # เก็บ centroids สำหรับเฟรมถัดไป
            LAST_FRAME_CENTROIDS = centroids
        elif VISION_COUNT_MODE == 'single':
            # โหมดเม็ดยาทีละเม็ด: นับเมื่อ transition 0 -> 1 และ debounce
            now_ts = time.time()
            if circle_count >= 1:
                single_present_frames += 1
                # ถ้ายังไม่เคยนับ (frames ถึงเกณฑ์ + debounce ผ่าน)
                if (single_present_frames == SINGLE_MIN_HOLD_FRAMES and
                    (now_ts - single_last_seen_at) > SINGLE_DEBOUNCE_SEC):
                    single_total += 1
                    single_last_seen_at = now_ts
            else:
                # reset counter เมื่อไม่มีเม็ดในเฟรม
                single_present_frames = 0

    # แสดงจำนวนวงกลมบนภาพ (ตัดการแสดงสถานะยาออกตามคำขอ)
    if VISION_COUNT_MODE == 'peak':
        overlay_text = f"Circles: {circle_count} peak={peak_count}"
    elif VISION_COUNT_MODE == 'cumulative':
        overlay_text = f"Circles: {circle_count} total={cumulative_count}"
    else:  # single
        overlay_text = f"Circles: {circle_count} single_total={single_total}"
    cv2.putText(frame, overlay_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255,0,0), 2)

    # วาดเส้น entrance และ feedback เมื่ออยู่ในโหมด cumulative
    if VISION_COUNT_MODE == 'cumulative':
        h, w = frame.shape[:2]
        y = ENTRANCE_LINE_Y
        if 0 < y < h:
            cv2.line(frame, (0, y), (w, y), (0, 255, 255), 2)
            cv2.putText(frame, f"ENTRY y={y}", (10, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,255), 2)
        # แสดง +N ชั่วคราว 0.8 วินาทีหลังนับเพิ่ม
        if last_increment_amount > 0 and (time.time() - last_increment_at) < 0.8:
            cv2.putText(frame, f"+{last_increment_amount}", (w-120, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0,200,0), 3)
    elif VISION_COUNT_MODE == 'single':
        # แสดงสถานะ debounce
        if single_present_frames > 0:
            cv2.putText(frame, f"holding {single_present_frames}f", (10, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,180,255), 2)
        cv2.putText(frame, f"debounce={SINGLE_DEBOUNCE_SEC}s", (10, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0,180,255), 2)

    cv2.imshow('Camera', frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
