# 2.3.2 State Diagram: สถานะการทำงานของอุปกรณ์ Node

## Node State Flow
```
[offline] → [online] → [ready] → [busy] → [ready]
    ↑         ↓         ↓         ↓         ↑
    └────[disconnected]  └──[processing]──┘
```

## Node State Descriptions

### 1. **offline**
- **เมื่อ**: Node ไม่ได้เชื่อมต่อ MQTT
- **สถานะ**: `online=0, ready=0`
- **การทำงาน**: ไม่สามารถรับคำสั่งได้
- **ต่อไป**: → `online` เมื่อเชื่อมต่อ

### 2. **online** 
- **เมื่อ**: Node เชื่อมต่อ MQTT แล้ว
- **สถานะ**: `online=1, ready=0`
- **การทำงาน**: เชื่อมต่อแล้วแต่ยังไม่พร้อม
- **ต่อไป**: → `ready` เมื่อ initialization เสร็จ

### 3. **ready**
- **เมื่อ**: Node พร้อมรับคำสั่งใหม่
- **สถานะ**: `online=1, ready=1`
- **การทำงาน**: สามารถรับ queue ใหม่ได้
- **ต่อไป**: → `busy` เมื่อได้รับคำสั่ง

### 4. **busy**
- **เมื่อ**: Node กำลังประมวลผล queue
- **สถานะ**: `online=1, ready=0`
- **การทำงาน**: ทำงานตาม queue, รอ IR detection
- **ต่อไป**: → `ready` เมื่อส่ง "done"

## Hardware State Flow (Arduino2)

### Operation State
```
[idle] → [operating] → [waiting_ir] → [completed] → [idle]
   ↑         ↓            ↓             ↓            ↑
   └─────[timeout]──────────────────────────────────┘
```

### Hardware Operations
```
STEP command → [isOperating=true] → Stepper motor running
ROOM command → [targetRoom=X] → Monitor IR sensor X
IR detected → [stopOperation] → Send "done" + Reset state
Timeout 30s → [stopOperation] → Send "done" + Reset state
```

## Database Tracking
```sql
-- Node state in database
CREATE TABLE node_status(
  node_id INTEGER PRIMARY KEY,
  online INTEGER NOT NULL DEFAULT 0,
  ready INTEGER NOT NULL DEFAULT 0,
  uptime INTEGER,
  last_seen DATETIME,
  last_ready_change DATETIME,
  last_online_change DATETIME
);
```

## Node Readiness Check
```python
# Server: mqtt_client.py
def _both_nodes_ready_db(max_age_sec=10, debounce_ms=500):
    """Check if both nodes ready with staleness + debounce"""
    # Must be: online=1, ready=1, recent last_seen, stable ready state
    return node1_ready and node2_ready and not_stale and stable
```

## MQTT Messages
```json
// Node announces ready
{"online": 1, "ready": 1, "uptime": 12345}

// Node becomes busy  
{"online": 1, "ready": 0, "uptime": 12346}

// Node completes work
{"queue_id": 1, "done": 1, "status": "success"}
```

## Arduino State Variables
```cpp
// arduino_2.ino - Simplified state
bool isOperating = false;        // Operating state
int targetRoom = -1;             // Target room (1,2,3)
int stepDirection = 0;           // Stepper direction
unsigned long operationStartTime = 0;  // For timeout
const unsigned long OPERATION_TIMEOUT = 30000; // 30s
```

## State Transitions
| Current | Event | Next | Action |
|---------|-------|------|--------|
| `offline` | MQTT connect | `online` | Publish online=1 |
| `online` | Setup complete | `ready` | Publish ready=1 |
| `ready` | Receive command | `busy` | Set ready=0, start work |
| `busy` | IR detected | `ready` | Send "done", set ready=1 |
| `busy` | Timeout 30s | `ready` | Send "done", set ready=1 |
| `any` | Disconnect | `offline` | Connection lost |