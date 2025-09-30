# 2.3.1 State Diagram: การทำงานของคิวระบบ

## Queue State Flow
```
[pending] → [in_progress] → [success]
    ↓              ↓            ↑
[failed] ←----[timeout]-------|
```

## State Descriptions

### 1. **pending**
- **เมื่อ**: User สร้าง queue ใหม่
- **การทำงาน**: รอการส่งไปยัง nodes
- **เงื่อนไข**: Both nodes ready
- **ต่อไป**: → `in_progress`

### 2. **in_progress** 
- **เมื่อ**: MQTT ส่งคำสั่งไป nodes แล้ว
- **การทำงาน**: Nodes กำลังประมวลผล
- **เงื่อนไข**: รอ "done" จาก both nodes
- **ต่อไป**: → `success` หรือ `failed`

### 3. **success**
- **เมื่อ**: Both nodes ส่ง "done" สำเร็จ
- **การทำงาน**: Queue เสร็จสิ้น
- **ผลลัพธ์**: served_at = timestamp
- **สถานะสุดท้าย**: ✅ เสร็จสิ้น

### 4. **failed**
- **เมื่อ**: Node ใดส่ง timeout/error มา
- **การทำงาน**: Queue ล้มเหลว
- **สาเหตุ**: node1:timeout, node2:failed, etc.
- **สถานะสุดท้าย**: ❌ ล้มเหลว

## Transition Conditions

| From | To | Condition | Action |
|------|----|-----------| -------|
| `pending` | `in_progress` | Both nodes ready | Send MQTT commands |
| `in_progress` | `success` | Both nodes "done" | Set served_at |
| `in_progress` | `failed` | Any node timeout/error | Log failure reason |
| `in_progress` | `failed` | 30s timeout | Mark as timeout |

## Database Tracking
```sql
-- Queue lifecycle events
INSERT INTO events(queue_id, event, message) VALUES
(1, 'created', '{"patient_id": 1, "items": [...]}'),
(1, 'ack_accepted', '{"queue_id": 1, "accepted": 1}'),
(1, 'evt_done_node1', '{"status": "success"}'),
(1, 'evt_done_node2', '{"status": "success"}'),
(1, 'queue_completed', 'Both nodes successful');
```

## Code Implementation
```python
# Server: mqtt_client.py
def _handle_node_completion_atomic(qid, node_id, status, payload):
    # Check if both nodes completed
    if node1_done and node2_done:
        if n1_st == 'success' and n2_st == 'success':
            conn.execute("UPDATE queues SET status=?, served_at=CURRENT_TIMESTAMP WHERE id=?", ('success', qid))
        else:
            conn.execute("UPDATE queues SET status=? WHERE id=?", ('failed', qid))
```