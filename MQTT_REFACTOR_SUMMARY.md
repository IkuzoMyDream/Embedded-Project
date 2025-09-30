# MQTT Dispatch Logic Refactor Summary

## ✅ **Changes Made**

### 1. **Database Schema Addition**
- **File**: `data/init.sql`
- **Added**: `node_status` table with persistent state tracking
```sql
CREATE TABLE IF NOT EXISTS node_status (
  node_id INTEGER PRIMARY KEY,
  online  INTEGER NOT NULL DEFAULT 0,
  ready   INTEGER NOT NULL DEFAULT 0,
  uptime  INTEGER,
  last_seen DATETIME,
  last_ready_change DATETIME,
  last_online_change DATETIME
);
```

### 2. **New DB Helper Functions**
- **File**: `server/mqtt_client.py`
- **Added Functions**:
  - `_upsert_node_state()` - Persist node state to DB with change tracking
  - `_both_nodes_ready_db()` - DB-based readiness check with staleness (10s) and debounce (500ms)

### 3. **Dispatcher Uses DB as Single Source of Truth**
- **Changed**: `_dispatch_next_queue()` now uses `_both_nodes_ready_db()` instead of in-memory flags
- **Logging**: Enhanced DB state logging for debugging dispatch blocks
- **Preserved**: FIFO ordering and single in_progress queue guarantees

### 4. **Auto-Dispatch on State Changes**
- **Changed**: STATE message handling now triggers auto-dispatch
- **Logic**: When both nodes ready (DB) + no in_progress + pending exists → immediate dispatch
- **Safety**: Error handling prevents auto-dispatch failures from breaking the system

### 5. **Readiness Watchdog Thread**
- **Added**: 2-second polling thread as defensive measure
- **Purpose**: Catch missed dispatch opportunities due to race conditions
- **Condition**: Both nodes ready (DB) + no in_progress + pending exists

### 6. **Memory Flags Retained for Logging Only**
- **Status**: `_node_ready` and `_node_online` kept for backward compatibility
- **Usage**: Legacy logging only - no dispatch decisions
- **Note**: Can be removed in future versions

## 🎯 **Key Benefits**

### ✅ **Database as Single Source of Truth**
- Node readiness persists across server restarts
- No more memory/DB state inconsistencies
- Atomic operations prevent race conditions

### ✅ **Staleness Protection**
- Max age check (10 seconds) prevents stale state decisions
- Debounce window (500ms) prevents rapid state change issues

### ✅ **Multiple Dispatch Triggers**
1. **STATE messages** → immediate auto-dispatch if ready
2. **Completion events** → next queue dispatch after both nodes done
3. **Watchdog thread** → safety net every 2 seconds
4. **Initial startup** → delayed dispatch after 3 seconds

### ✅ **Preserved Guarantees**
- **FIFO**: Lowest queue.id first (unchanged)
- **Single in_progress**: BEGIN IMMEDIATE + NOT EXISTS check (unchanged)
- **Atomicity**: All DB operations in transactions (unchanged)

## 🔧 **Configuration**

### **Timing Parameters**:
```python
_both_nodes_ready_db(max_age_sec=10, debounce_ms=500)
```
- `max_age_sec=10`: Node must report within 10 seconds
- `debounce_ms=500`: Wait 500ms after ready state change

### **Watchdog Frequency**:
```python
time.sleep(2)  # Check every 2 seconds
```

## 📊 **Expected Behavior**

### **Normal Operation**:
1. Node sends `{"ready": 1, "online": 1}` → DB updated → auto-dispatch if pending
2. Both nodes complete queue → DB checked → next queue dispatched if ready
3. Watchdog ensures no queues stuck waiting

### **Edge Cases Handled**:
- **Server restart**: Node state persists in DB
- **Stale connections**: max_age_sec prevents dispatch to dead nodes
- **Rapid state changes**: debounce_ms prevents instability
- **Missed events**: Watchdog thread provides backup dispatch

### **Debug Information**:
- Enhanced logging shows DB state when dispatch blocked
- All node state changes logged with timestamps
- Auto-dispatch attempts logged with reasons

## 🚀 **Migration Notes**

### **Backward Compatibility**:
- All MQTT topics, payloads, and API routes unchanged
- Existing nodes continue working without modification
- Log format preserved for monitoring tools

### **Database Migration**:
- New `node_status` table created automatically on startup
- No data migration needed (fresh state tracking)
- Safe to deploy without downtime

This refactor eliminates the race condition issues while maintaining all existing functionality and performance characteristics.