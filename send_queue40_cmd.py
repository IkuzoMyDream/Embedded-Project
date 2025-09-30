# -*- coding: utf-8 -*-
import paho.mqtt.client as mqtt, json, time
print("=== SEND CMD QUEUE 40 (items 4+1=5) ===")
c = mqtt.Client()
c.connect("127.0.0.1",1883,60)
c.loop_start()
payload = {
    "queue_id": 41,
    "queue_number": "41",
    "target_room": 1,
    "items": [
        {"pill_id": 1, "quantity": 4},
        {"pill_id": 2, "quantity": 1}
    ]
}
c.publish("disp/cmd/2", json.dumps(payload), qos=1)
print("Command sent disp/cmd/2")
time.sleep(1)
c.loop_stop()
