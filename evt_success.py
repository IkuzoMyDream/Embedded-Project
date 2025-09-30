# -*- coding: utf-8 -*-
import paho.mqtt.client as mqtt, json, time

print("สง evt success สำหรบ queue 40")
c = mqtt.Client()
c.connect("127.0.0.1", 1883, 60)
c.loop_start()

evt = {
    "queue_id": 40,
    "done": 1,
    "status": "success"
}

c.publish("disp/evt/2", json.dumps(evt), qos=1)
print("สง evt success เรยบรอย")
time.sleep(1)
c.loop_stop()
