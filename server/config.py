import os
from dotenv import load_dotenv
load_dotenv()

FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "app.db"))
INIT_SQL = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "init.sql"))

MQTT_BROKER = os.getenv("MQTT_BROKER", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID", "odroid-flask")
MQTT_TOPIC_CMD = os.getenv("MQTT_TOPIC_CMD", "dispense/queue/cmd")
MQTT_TOPIC_ACK = os.getenv("MQTT_TOPIC_ACK", "dispense/queue/ack")
