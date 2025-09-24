# Smart Dispense (Odroid)

## Dev (laptop)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit if needed
python - <<'PY'
from server.db import init_db; init_db()
PY
python -m server.app
# open: http://localhost:5000/pages/dashboard.html
# or:   http://localhost:5000/pages/queue_management.html

## Odroid (production-ish)
sudo apt update && sudo apt install -y mosquitto mosquitto-clients git python3-venv
git clone <your_repo_url>.git smart-dispense && cd smart-dispense
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # set MQTT_BROKER=127.0.0.1
python - <<'PY'
from server.db import init_db; init_db()
PY
# run
python -m server.app

## MQTT topics
- publish cmd:  ${MQTT_TOPIC_CMD}  payload: {"queue_id", "patient_id", "pill_id", "target_room"}
- device ack:   ${MQTT_TOPIC_ACK}  payload: {"queue_id", "status":"success|failed", "detail": "..."}
