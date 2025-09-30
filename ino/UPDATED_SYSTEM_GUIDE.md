# Updated NodeMCU-Arduino Communication System

## Overview
The system has been updated from GPIO-based logic communication to Serial-based command communication, providing more flexibility and better control.

## Key Changes

### 1. Arduino Controller (`arduino_1.ino`)
- **OLD**: Read digital logic levels from NodeMCU pins
- **NEW**: Receive CSV commands via Serial communication

#### Communication Protocol:
```
NodeMCU -> Arduino Commands:
- "queue_id,pill_id,quantity" - Dispense pills
- "DC,0" or "DC,1" - Control DC motor
- "SERVO,id,position" - Control specific servo

Arduino -> NodeMCU Response:
- "done" - Operation completed successfully
```

#### Features Added:
- **Smooth servo movement** - Uses your example logic with gradual position changes
- **Pill dispensing logic** - Maps pill IDs to specific servos (13→servo1, 15→servo2)
- **Command parsing** - Handles multiple command formats
- **Error handling** - Validates commands and provides feedback

### 2. NodeMCU Controller (`node_mcu_1.ino`)
- **OLD**: Send GPIO logic levels to Arduino
- **NEW**: Send Serial commands and wait for responses

#### Features Added:
- **Command forwarding** - Converts MQTT commands to Serial format
- **Response handling** - Waits for Arduino "done" confirmation
- **Timeout protection** - 30-second timeout if Arduino doesn't respond
- **Better state management** - Tracks busy/ready status more accurately

## Hardware Connections

### Serial Communication:
```
NodeMCU ESP8266    Arduino Uno
GND           <->  GND
TX (GPIO1)    <->  RX (Pin 0)
RX (GPIO3)    <->  TX (Pin 1)
```

### Arduino Servo Connections:
```
Servo 1  -> Pin 9
Servo 2  -> Pin 10
Servo 3  -> Pin 11
Servo 4  -> Pin 12
DC Motor -> Pin 8 (Enable), Pin 7 (Direction)
```

## Servo Control Logic

Based on your example, the system implements smooth servo movement:

### Pill ID Mapping:
- **Pill ID 13**: Controls Servo 1, moves to 120° (open) then back to 60° (closed)
- **Pill ID 15**: Controls Servo 2, moves to 120° (open) then back to 60° (closed)
- **Other IDs**: Default to Servo 1

### Smooth Movement:
```cpp
void smoothMove(Servo &servo, int startPos, int endPos) {
  if (startPos < endPos) {
    for (int pos = startPos; pos <= endPos; pos++) {
      servo.write(pos);
      delay(2);  // Smooth movement
    }
  } else {
    for (int pos = startPos; pos >= endPos; pos--) {
      servo.write(pos);
      delay(2);
    }
  }
}
```

## MQTT Command Examples

### Dispense Pills:
```json
{
  "queue_id": 1,
  "items": [
    {"pill_id": 13, "quantity": 2},
    {"pill_id": 15, "quantity": 1}
  ]
}
```

### Control Servo Directly:
```json
{
  "queue_id": 2,
  "op": "servo",
  "id": 1,
  "on": 1
}
```

### Control DC Motor:
```json
{
  "queue_id": 3,
  "op": "dc",
  "on": 1
}
```

## Advantages of New System

1. **More Flexible**: Can send complex commands with multiple parameters
2. **Better Debugging**: Serial communication provides clear command/response logging
3. **Scalable**: Easy to add new command types
4. **Robust**: Timeout handling prevents system lockup
5. **Production Ready**: Based on your test code but enhanced for real usage

## Configuration Notes

### Baud Rate:
- Both NodeMCU and Arduino use **9600 baud** for serial communication
- Make sure both devices are configured with the same baud rate

### Servo Positions:
- **SERVO_CLOSED = 60°** - Adjust based on your mechanical setup
- **SERVO_OPEN = 120°** - Adjust based on your mechanical setup

### WiFi/MQTT Settings:
- WIFI_SSID: "HAZANO.my"
- MQTT_HOST: "172.20.10.2"
- Adjust these in the NodeMCU code as needed

## Testing the System

1. **Upload Arduino code** to Arduino Uno
2. **Upload NodeMCU code** to ESP8266
3. **Connect via Serial** between devices
4. **Send MQTT commands** to test functionality
5. **Monitor Serial output** on both devices for debugging

The system now provides a robust foundation for your pill dispensing project with smooth servo control and reliable communication.