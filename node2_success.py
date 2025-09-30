# -*- coding: utf-8 -*-
import paho.mqtt.client as mqtt, json, time
print("=== SIM NODE2 SUCCESS (queue 40) ===")
c = mqtt.Client()
c.connect("127.0.0.1",1883,60)
c.loop_start()
evt = {"queue_id": 41, "done": 1, "status": "success"}
c.publish("disp/evt/2", json.dumps(evt), qos=1)
print("Published node2 success")
time.sleep(1)
c.loop_stop()
