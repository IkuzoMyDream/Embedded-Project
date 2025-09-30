# Arduino1 Pill ID Mapping System

## Updated Pill ID to Servo Mapping

### Direct Mapping System:
```
pill_id 1  ->  Servo 1  ->  Pin 9
pill_id 2  ->  Servo 2  ->  Pin 10
pill_id 3  ->  Servo 3  ->  Pin 11
pill_id 4  ->  Servo 4  ->  Pin 12
```

## Hardware Connections

### Arduino Servo Outputs:
```
Servo 1 (pill_id 1)  ->  Pin 9
Servo 2 (pill_id 2)  ->  Pin 10
Servo 3 (pill_id 3)  ->  Pin 11
Servo 4 (pill_id 4)  ->  Pin 12
DC Motor Enable      ->  Pin 8
DC Motor Direction   ->  Pin 7
```

### SoftwareSerial Communication:
```
NodeMCU D6 (TX)  ->  Arduino Pin 2 (RX)
NodeMCU D7 (RX)  ->  Arduino Pin 3 (TX)
GND              ->  GND
```

## Command Examples

### Pill Dispensing Commands:
```
"1,1,2"    // queue_id=1, pill_id=1, quantity=2 -> Use Servo 1
"2,2,1"    // queue_id=2, pill_id=2, quantity=1 -> Use Servo 2
"3,3,3"    // queue_id=3, pill_id=3, quantity=3 -> Use Servo 3
"4,4,1"    // queue_id=4, pill_id=4, quantity=1 -> Use Servo 4
```

### Direct Servo Control:
```
"SERVO,1,120"  // Move Servo 1 to position 120°
"SERVO,2,60"   // Move Servo 2 to position 60°
"SERVO,3,90"   // Move Servo 3 to position 90°
"SERVO,4,45"   // Move Servo 4 to position 45°
```

### DC Motor Control:
```
"DC,1"     // Turn DC motor ON
"DC,0"     // Turn DC motor OFF
```

## MQTT Command Examples

### Single Pill Dispensing:
```json
{
  "queue_id": 1,
  "pill_id": 1,
  "quantity": 2
}
```

### Multiple Pills (Items Array):
```json
{
  "queue_id": 2,
  "items": [
    {"pill_id": 1, "quantity": 1},
    {"pill_id": 2, "quantity": 2},
    {"pill_id": 3, "quantity": 1}
  ]
}
```

### Direct Servo Control via MQTT:
```json
{
  "queue_id": 3,
  "op": "servo",
  "id": 1,
  "on": 1
}
```

## Code Structure

### Pill Dispensing Logic:
```cpp
void actuatePill(int queueId, int pillId, int quantity) {
  // Direct mapping: pill_id = servo number
  if (pillId >= 1 && pillId <= 4) {
    controlServo(pillId, SERVO_OPEN);      // Open servo
    delay(500 * quantity);                 // Dispense time
    controlServo(pillId, SERVO_CLOSED);    // Close servo
  }
}
```

### Reserved Servo Logic Functions:
```cpp
void servoLogic1() { /* Reserved for pill type 1 specific logic */ }
void servoLogic2() { /* Reserved for pill type 2 specific logic */ }
void servoLogic3() { /* Reserved for pill type 3 specific logic */ }
void servoLogic4() { /* Reserved for pill type 4 specific logic */ }
```

## Serial Monitor Output Example

### Arduino1 Monitor:
```
[ARDUINO] Production controller ready
[ARDUINO] Using SoftwareSerial on pins 2(RX) and 3(TX)
[ARDUINO] Pill ID Mapping:
  pill_id 1 -> Servo 1 (Pin 9)
  pill_id 2 -> Servo 2 (Pin 10)
  pill_id 3 -> Servo 3 (Pin 11)
  pill_id 4 -> Servo 4 (Pin 12)

[CMD] Received: 1,2,1
[PILL] Processing queue_id=1 pill_id=2 qty=1
[PILL] Dispensing pill_id 2 using servo 2
[SERVO] Moving servo 2 from 60 to 120
[SERVO] Moving servo 2 from 120 to 60
[PILL] Dispensing complete
done
```

## Advantages of Direct Mapping

1. **Simple Logic**: pill_id directly corresponds to servo number
2. **Easy to Remember**: pill_id 1 = servo 1, pill_id 2 = servo 2, etc.
3. **Scalable**: Easy to add more servos (up to 4 supported)
4. **Clear Documentation**: Obvious mapping for maintenance
5. **Future Expansion**: Reserved servo logic functions for custom behavior

## Validation

### Valid pill_id Range: 1-4
- **pill_id 1**: Uses Servo 1 (Pin 9)
- **pill_id 2**: Uses Servo 2 (Pin 10)
- **pill_id 3**: Uses Servo 3 (Pin 11)
- **pill_id 4**: Uses Servo 4 (Pin 12)

### Invalid pill_id:
- **pill_id < 1 or > 4**: Error message, no servo action

## Testing Procedure

1. **Connect Hardware**: Wire servos to pins 9-12
2. **Upload Code**: Flash Arduino1 code
3. **Test Manual Commands**: Use Serial Monitor to send commands
4. **Test MQTT Commands**: Send JSON payloads via MQTT
5. **Verify Mapping**: Confirm pill_id matches correct servo

This system provides a clean, direct mapping between pill types and their corresponding servo dispensers! 🎯