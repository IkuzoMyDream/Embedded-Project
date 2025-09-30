# Updated NodeMCU-Arduino Communication with SoftwareSerial

## Hardware Connections

### SoftwareSerial Wiring:
```
NodeMCU ESP8266      Arduino Uno
D6 (GPIO12) TX  <->  Pin 2 (RX)
D7 (GPIO13) RX  <->  Pin 3 (TX)
GND             <->  GND
```

### USB Connections:
- **NodeMCU**: Connect to computer USB for programming and MQTT monitoring
- **Arduino**: Connect to computer USB for programming and servo monitoring
- Both devices can be connected simultaneously to the same computer

### Servo/Actuator Connections (Arduino):
```
Servo 1  -> Pin 9
Servo 2  -> Pin 10
Servo 3  -> Pin 11
Servo 4  -> Pin 12
DC Motor -> Pin 8 (Enable), Pin 7 (Direction)
```

## Key Changes Made

### 1. Arduino Code (`arduino_1.ino`)
- Added `#include <SoftwareSerial.h>`
- Added pins: `PIN_RX = 2`, `PIN_TX = 3`
- Created `SoftwareSerial nodeSerial(PIN_RX, PIN_TX)`
- **USB Serial (9600 baud)**: For monitoring/debugging via Arduino IDE Serial Monitor
- **SoftwareSerial (9600 baud)**: For communication with NodeMCU
- All responses now sent to both Serial and nodeSerial

### 2. NodeMCU Code (`node_mcu_1.ino`)
- Added `#include <SoftwareSerial.h>`
- Added pins: `PIN_TX_TO_ARDUINO = D6`, `PIN_RX_FROM_ARDUINO = D7`
- Created `SoftwareSerial arduinoSerial(PIN_RX_FROM_ARDUINO, PIN_TX_TO_ARDUINO)`
- **USB Serial (9600 baud)**: For WiFi/MQTT monitoring via NodeMCU Serial Monitor
- **SoftwareSerial (9600 baud)**: For communication with Arduino
- Commands sent via SoftwareSerial, responses read from SoftwareSerial

## Benefits

1. **Dual USB Connection**: Both devices can be programmed and monitored simultaneously
2. **Independent Debugging**: Monitor NodeMCU MQTT traffic and Arduino servo actions separately
3. **No Conflict**: USB Serial and SoftwareSerial operate independently
4. **Easy Testing**: Can test Arduino commands manually via its USB Serial Monitor
5. **Production Ready**: Real-world deployment with separate power sources

## Serial Communication Protocol

### NodeMCU -> Arduino Commands:
```
"1,13,2"           // queue_id=1, pill_id=13, quantity=2
"DC,1"             // Turn DC motor ON
"DC,0"             // Turn DC motor OFF
"SERVO,1,120"      // Move servo 1 to position 120°
"SERVO,2,60"       // Move servo 2 to position 60°
```

### Arduino -> NodeMCU Response:
```
"done"             // Operation completed successfully
```

## Testing Steps

### 1. Upload Code:
- Upload `arduino_1.ino` to Arduino Uno
- Upload `node_mcu_1.ino` to NodeMCU ESP8266

### 2. Wire Connections:
- Connect D6(TX) to Pin 2(RX)
- Connect D7(RX) to Pin 3(TX)
- Connect GND to GND

### 3. Monitor Both Devices:
- Open Arduino IDE Serial Monitor for Arduino (COM port of Arduino)
- Open another Arduino IDE Serial Monitor for NodeMCU (COM port of NodeMCU)
- Set both to 9600 baud

### 4. Test Communication:
- Send MQTT commands to NodeMCU
- Watch command forwarding in NodeMCU monitor
- Watch command execution in Arduino monitor
- Verify "done" responses

### 5. Manual Testing (Arduino):
In Arduino Serial Monitor, you can manually type commands to test:
```
1,13,2      // Test pill dispensing
DC,1        // Test DC motor
SERVO,1,90  // Test servo movement
```

## MQTT Command Examples

### Test Pill Dispensing:
```json
Topic: disp/cmd/1
Payload: {
  "queue_id": 1,
  "items": [
    {"pill_id": 13, "quantity": 2}
  ]
}
```

### Test Servo Control:
```json
Topic: disp/cmd/1
Payload: {
  "queue_id": 2,
  "op": "servo",
  "id": 1,
  "on": 1
}
```

### Test DC Motor:
```json
Topic: disp/cmd/1
Payload: {
  "queue_id": 3,
  "op": "dc",
  "on": 1
}
```

This setup allows you to have both devices connected to the same computer via USB while maintaining reliable SoftwareSerial communication between them for your pill dispensing system.