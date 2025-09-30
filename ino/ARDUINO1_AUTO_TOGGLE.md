# Arduino1 Auto-Toggle Servo System

## Updated Features

### 🔄 **Auto Toggle Logic**
- แต่ละ servo จะ **เปิด-ปิด อัตโนมัติ** เมื่อได้รับคำสั่ง
- ไม่ต้อง input หลายครั้ง servo จะ toggle เอง
- แต่ละ servo มี timing แตกต่างกัน

### ⚡ **Auto DC Motor**
- **DC motor เปิดอัตโนมัติ** ทุกครั้งที่มี pill request
- ไม่ต้องส่งคำสั่ง DC แยก

## Servo Logic Details

### 🎯 **Servo Mapping & Timing:**
```
pill_id 1 -> Servo 1 (Pin 9)  -> 500ms hold time
pill_id 2 -> Servo 2 (Pin 10) -> 700ms hold time  
pill_id 3 -> Servo 3 (Pin 11) -> 300ms hold time
pill_id 4 -> Servo 4 (Pin 12) -> 600ms hold time
```

### 🔄 **Toggle Sequence:**
1. **เปิด**: Smooth move จาก current position -> 120°
2. **หน่วง**: รอตาม timing ของแต่ละ servo
3. **ปิด**: Smooth move จาก 120° -> 60°

## Code Implementation

### Servo Logic Functions:
```cpp
void servoLogic1() {
  // Servo 1: 500ms hold time
  smoothMove(servo1, servo1.read(), 120);  // เปิด
  delay(500);                              // หน่วงเวลา
  smoothMove(servo1, servo1.read(), 60);   // ปิด
}

void servoLogic2() {
  // Servo 2: 700ms hold time (longer for different pill type)
  smoothMove(servo2, servo2.read(), 120);  // เปิด
  delay(700);                              // หน่วงเวลานานกว่า
  smoothMove(servo2, servo2.read(), 60);   // ปิด
}

void servoLogic3() {
  // Servo 3: 300ms hold time (shorter/faster)
  smoothMove(servo3, servo3.read(), 120);  // เปิด
  delay(300);                              // หน่วงเวลาสั้น
  smoothMove(servo3, servo3.read(), 60);   // ปิด
}

void servoLogic4() {
  // Servo 4: 600ms hold time (medium timing)
  smoothMove(servo4, servo4.read(), 120);  // เปิด
  delay(600);                              // หน่วงเวลาปานกลาง
  smoothMove(servo4, servo4.read(), 60);   // ปิด
}
```

### Auto DC & Quantity Handling:
```cpp
void actuatePill(int queueId, int pillId, int quantity) {
  // Auto DC ON
  setDcState(true);
  
  // Execute servo logic for each quantity
  for (int i = 0; i < quantity; i++) {
    switch (pillId) {
      case 1: servoLogic1(); break;
      case 2: servoLogic2(); break;
      case 3: servoLogic3(); break;
      case 4: servoLogic4(); break;
    }
    if (i < quantity - 1) delay(200); // pause between cycles
  }
}
```

## Command Examples

### 📡 **MQTT Commands:**
```json
{
  "queue_id": 1,
  "pill_id": 1,
  "quantity": 2
}
```
**Result**: DC ON + Servo1 toggle 2 ครั้ง (500ms hold แต่ละครั้ง)

```json
{
  "queue_id": 2,
  "pill_id": 2,
  "quantity": 1
}
```
**Result**: DC ON + Servo2 toggle 1 ครั้ง (700ms hold)

### 🔧 **Serial Commands:**
```
1,1,3     // pill_id=1, quantity=3 -> Servo1 toggle 3 ครั้ง + DC ON
2,2,1     // pill_id=2, quantity=1 -> Servo2 toggle 1 ครั้ง + DC ON
3,3,2     // pill_id=3, quantity=2 -> Servo3 toggle 2 ครั้ง + DC ON
4,4,1     // pill_id=4, quantity=1 -> Servo4 toggle 1 ครั้ง + DC ON
```

## Serial Monitor Output

### Example Output for `1,1,2`:
```
[CMD] Received: 1,1,2
[PILL] Processing queue_id=1 pill_id=1 qty=2
[AUTO] Turning ON DC motor for pill dispensing
[DC] state set to 1
[PILL] Dispensing pill_id 1 using servo 1 (quantity: 2)
[PILL] Dispensing cycle 1 of 2

[SERVO1] Starting toggle sequence...
Servo1 ขยับไปที่ 120° แบบ smooth... เปิด
[SMOOTH] Moving from 60° to 120°
[SMOOTH] Reached position 120°
Servo1 ขยับไปที่ 60° แบบ smooth... ปิด
[SMOOTH] Moving from 120° to 60°
[SMOOTH] Reached position 60°
[SERVO1] Toggle sequence complete

[PILL] Dispensing cycle 2 of 2

[SERVO1] Starting toggle sequence...
Servo1 ขยับไปที่ 120° แบบ smooth... เปิด
[SMOOTH] Moving from 60° to 120°
[SMOOTH] Reached position 120°
Servo1 ขยับไปที่ 60° แบบ smooth... ปิด
[SMOOTH] Moving from 120° to 60°
[SMOOTH] Reached position 60°
[SERVO1] Toggle sequence complete

[PILL] Dispensing complete
done
```

## Key Improvements

### ✅ **Auto Features:**
1. **DC Motor**: เปิดอัตโนมัติทุกครั้งที่มี pill request
2. **Toggle Logic**: servo เปิด-ปิดเอง ไม่ต้อง manual control
3. **Quantity Support**: repeat toggle ตาม quantity ที่กำหนด

### ⚙️ **Customizable Timing:**
- แต่ละ servo มี hold time ต่างกัน
- สามารถปรับ delay ในแต่ละ servoLogic function ได้
- Smooth movement ใช้ delay(2) เหมือนตัวอย่างที่ให้มา

### 🔧 **Easy Maintenance:**
- แต่ละ servo มี function แยกกัน
- ง่ายต่อการปรับแต่ง timing ของแต่ละ pill type
- Clear logging สำหรับ debugging

ตอนนี้ระบบทำงานแบบ **One Command, Full Auto!** 🎉