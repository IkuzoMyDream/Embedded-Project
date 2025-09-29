import cv2
import numpy as np

# เปิดกล้อง
cap = cv2.VideoCapture(0)

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
