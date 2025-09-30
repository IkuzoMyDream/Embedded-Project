# NodeMCU2-Arduino2 Communication System

## Overview
NodeMCU2 และ Arduino2 ใช้ concept เดียวกันกับ NodeMCU1-Arduino1 โดยใช้ SoftwareSerial communication และต้องรอ "done" จาก Arduino ก่อนส่ง MQTT event

## Hardware Connections

### SoftwareSerial Wiring:
```
NodeMCU ESP8266      Arduino Uno
D6 (GPIO12) TX  <->  Pin 2 (RX)
D7 (GPIO13) RX  <->  Pin 3 (TX)
GND             <->  GND
```

### Arduino2 Actuator Connections:
```
Servo 5      -> Pin 9
Servo 6      -> Pin 10
Pump         -> Pin 11
DC Motor EN  -> Pin 8
DC Motor DIR -> Pin 7
Stepper STEP -> Pin 5
Stepper DIR  -> Pin 6
Sensor       -> Pin 4 (INPUT_PULLUP)
```

## Communication Protocol

### NodeMCU2 -> Arduino2 Commands:
```
"DIR,L"        // Set stepper direction LEFT
"DIR,R"        // Set stepper direction RIGHT
"SERVO5,1"     // Trigger servo 5
"SERVO6,1"     // Trigger servo 6
"PUMP,1"       // Turn pump ON
"PUMP,0"       // Turn pump OFF
"DC,1"         // Turn DC motor ON
"DC,0"         // Turn DC motor OFF
```

### Arduino2 -> NodeMCU2 Response:
```
"done"         // Command completed successfully
"sensor_done"  // Sensor triggered completion
"1"            // Sensor value
```

## MQTT Topics & Payloads

### Subscribe Topic: `disp/cmd/2`
```json
{
  "queue_id": 123,
  "target_room": 1    // Room 1, 2, or 3
}
```

### Publish Topics:
- **ACK**: `disp/ack/2` - Command acknowledgment
- **EVT**: `disp/evt/2` - Completion event
- **STATE**: `disp/state/2` - Node status (retained)

## Room Logic

### Room 1:
- Direction: LEFT (`DIR,L`)
- DC motor activation (`DC,1`)

### Room 2:
- Direction: RIGHT (`DIR,R`)
- Servo 5 trigger (`SERVO5,1`)
- DC motor activation (`DC,1`)

### Room 3:
- Direction: RIGHT (`DIR,R`)
- Servo 6 trigger (`SERVO6,1`)
- Pump activation (`PUMP,1`)
- DC motor activation (`DC,1`)

## Key Features

### 1. Command Sequencing
- NodeMCU2 ส่งคำสั่งหลายคำสั่งตาม target_room
- ใช้ `pendingCommands` counter เพื่อติดตาม
- รอ "done" จากทุกคำสั่งก่อนส่ง MQTT event

### 2. Sensor Integration
- Arduino2 มี sensor ที่ pin 4
- เมื่อ sensor trigger จะส่ง "sensor_done"
- สามารถใช้แทน DC completion ได้

### 3. Timeout Protection
- 30 วินาที timeout สำหรับการรอ Arduino response
- หาก timeout จะส่ง event "timeout" status

### 4. Dual USB Support
- Arduino2: USB สำหรับ programming/monitoring
- NodeMCU2: USB สำหรับ WiFi/MQTT monitoring
- SoftwareSerial สำหรับการสื่อสารระหว่างกัน

## Testing Commands

### MQTT Test Commands:

#### Room 1 Test:
```json
{
  "queue_id": 1,
  "target_room": 1
}
```
**Arduino sequence**: DIR,L -> DC,1

#### Room 2 Test:
```json
{
  "queue_id": 2,
  "target_room": 2
}
```
**Arduino sequence**: DIR,R -> SERVO5,1 -> DC,1

#### Room 3 Test:
```json
{
  "queue_id": 3,
  "target_room": 3
}
```
**Arduino sequence**: DIR,R -> SERVO6,1 -> PUMP,1 -> DC,1

#### Force Complete Test:
```json
{
  "queue_id": 999,
  "target_room": 1,
  "force": true
}
```

### Arduino2 Manual Test Commands:
สามารถทดสอบ Arduino2 ผ่าน Serial Monitor:
```
DIR,L
DIR,R
SERVO5,1
SERVO6,1
PUMP,1
PUMP,0
DC,1
DC,0
```

## Serial Monitor Output Examples

### NodeMCU2 Monitor:
```
[NODE2] Production MQTT->Arduino bridge starting
[NODE2] Using SoftwareSerial - TX:D6(GPIO12), RX:D7(GPIO13)
[WiFi] OK 192.168.1.100
[MQTT] connecting... OK
[NODE2] Ready to receive MQTT commands and forward to Arduino
[MQTT] disp/cmd/2 | 45 bytes
[NODE] Processing queue 1 for target_room 2
[ARDUINO] Sending: DIR,R
[ARDUINO] Sending: SERVO5,1
[ARDUINO] Sending: DC,1
[NODE] Sent 3 commands to Arduino, waiting for responses...
[ARDUINO] Response: done
[NODE] Arduino response received, pending: 2
[ARDUINO] Response: done
[NODE] Arduino response received, pending: 1
[ARDUINO] Response: done
[NODE] All Arduino commands completed for queue 1
[MQTT] EVT sent - queue_id=1 status=success
```

### Arduino2 Monitor:
```
[ARDUINO2] Production controller ready
[CMD] Received: DIR,R
[STEP] Direction: RIGHT
done
[CMD] Received: SERVO5,1
[SERVO5] Triggered
done
[CMD] Received: DC,1
[DC] State set to 1
[DC] Starting actuator sequence...
[DC] Sequence complete
done
```

## Comparison with Node1/Arduino1

### Similarities:
- SoftwareSerial communication (pins 2,3)
- "done" response requirement
- MQTT topics structure
- Timeout protection
- Dual USB support

### Differences:
- **Node2**: Multiple commands per MQTT message
- **Node2**: Command counter (`pendingCommands`)
- **Node2**: Room-based logic instead of pill-based
- **Node2**: Sensor integration for completion detection
- **Arduino2**: Different actuators (stepper, pump vs servos)

นี่คือระบบที่สมบูรณ์และใช้ concept เดียวกันกับ Node1 แต่ปรับให้เหมาะกับการทำงานของ Node2! 🎉