import cv2
import numpy as np
import time
import threading
import requests
import os
import collections
import statistics

API_BASE = os.environ.get('DISPENSE_API_BASE', 'http://localhost:5000')
POST_INTERVAL_SEC = float(os.environ.get('VISION_POST_INTERVAL', '2.0'))  # ช่วงเวลาขั้นต่ำระหว่างโพสต์

# การตั้งค่าการทำให้ค่าคงที่ (stabilization)
STABILIZE_WINDOW = int(os.environ.get('VISION_STABILIZE_WINDOW', '7'))  # จำนวนเฟรมย้อนหลัง
STABLE_METHOD = os.environ.get('VISION_STABLE_METHOD', 'mode')  # mode | median | mean

# พักหลังนับครบ (คงที่เท่ากับ expected) เพื่อไม่สแปม (วินาที)
PAUSE_AFTER_MATCH = float(os.environ.get('VISION_PAUSE_AFTER_MATCH', '15.0'))

# หาก stable count เดิมซ้ำ และเพิ่งส่งไป ไม่ต้องส่งอีกในช่วง Quiet TTL
QUIET_SAMPLE_TTL = float(os.environ.get('VISION_QUIET_SAMPLE_TTL', '20.0'))

# ตรวจคิวใหม่ทุก ๆ n วินาที
QUEUE_POLL_INTERVAL = float(os.environ.get('VISION_QUEUE_POLL_INTERVAL', '3.0'))

last_post_at = 0.0
latest_frame_count = 0         # ค่าจำนวนล่าสุดจากเฟรมดิบ
stable_count = None            # ค่าหลังทำให้คงที่ (mode/median/mean)
last_stable_sent = None        # ค่าที่ส่งล่าสุด
stable_buffer = collections.deque(maxlen=STABILIZE_WINDOW)
lock = threading.Lock()

# ข้อมูลคิวปัจจุบันที่กำลัง dispense
current_queue_id = None
current_queue_number = None
expected_total = None
last_queue_poll = 0.0
paused_until = 0.0

def fetch_current_queue():
    global current_queue_id, expected_total, last_queue_poll, current_queue_number
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
    if current_queue_id is None:
        return False
    if stable_count is None:
        return False
    if now < paused_until:
        return False
    if stable_count == last_stable_sent and (now - last_post_at) < QUIET_SAMPLE_TTL:
        return False
    if (now - last_post_at) < POST_INTERVAL_SEC:
        return False
    return True

def poster_loop():
    global last_post_at, last_stable_sent, paused_until
    while True:
        time.sleep(0.25)
        now = time.time()
        if now - last_queue_poll > QUEUE_POLL_INTERVAL:
            fetch_current_queue()
        compute_stable()
        # ถ้าได้ค่า stable ตรงกับ expected แล้วพัก
        if current_queue_id and expected_total is not None and stable_count is not None:
            if stable_count == expected_total and now >= paused_until:
                paused_until = now + PAUSE_AFTER_MATCH
                print(f"[vision] match expected={expected_total} -> pause {PAUSE_AFTER_MATCH}s")
        if not should_post(now):
            continue
        try:
            payload = {"count_detected": stable_count}
            r = requests.post(f"{API_BASE}/api/vision/current", json=payload, timeout=2.0)
            last_post_at = now
            if r.status_code == 200:
                data = r.json()
                note = data.get('note')
                qid = data.get('queue_id')
                print(f"[vision] post stable={stable_count} -> queue {qid} | {note}")
                last_stable_sent = stable_count
            else:
                if r.status_code not in (404, 429):
                    print(f"[vision] server {r.status_code}: {r.text[:100]}")
        except Exception:
            pass

threading.Thread(target=poster_loop, daemon=True).start()

# เปิดกล้อง (CAM_INDEX override ผ่าน ENV ได้)
CAM_INDEX = int(os.environ.get('VISION_CAM_INDEX', '1'))
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

    # แสดงจำนวนวงกลมบนภาพ
    cv2.putText(
        frame,
        f"Circles detected: {circle_count}",
        (10, 30),                    # ตำแหน่งข้อความ
        cv2.FONT_HERSHEY_SIMPLEX,    # ฟอนต์
        1,                           # ขนาดฟอนต์
        (255, 0, 0),                 # สี (B,G,R)
        2                            # ความหนาเส้น
    )

    cv2.imshow('Camera', frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
