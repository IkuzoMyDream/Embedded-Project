from flask import Flask, send_from_directory, request, jsonify
from flask_cors import CORS
import json
from .db import init_db, query, execute
from .config import FLASK_HOST, FLASK_PORT, MQTT_TOPIC_CMD
from .mqtt_client import get_client

app = Flask(__name__, static_folder="../client/static", static_url_path="/static")
CORS(app)

# ---- serve pages ----
@app.route("/")
def root():
    return send_from_directory("../client/pages", "dashboard.html")

@app.route("/pages/<path:page>")
def pages(page):
    return send_from_directory("../client/pages", page)

# ---- API: basic reads ----
@app.get("/api/dashboard")
def api_dashboard():
    current = query("""
      SELECT q.id AS queue_id, p.name AS patient_name, r.name AS room, q.status
      FROM queues q
      JOIN patients p ON p.id=q.patient_id
      JOIN rooms r ON r.id=q.target_room
      WHERE q.status IN ('pending','sent')
      ORDER BY q.created_at ASC LIMIT 1
    """)
    logs = query("SELECT id, queue_id, ts, event, message FROM events ORDER BY id DESC LIMIT 50")
    success_count = query("SELECT COUNT(*) AS cnt FROM queues WHERE status='success'")[0]["cnt"]
    return jsonify({"current": current[0] if current else None, "logs": logs, "success_count": success_count})

@app.get("/api/lookup")
def api_lookup():
    return jsonify({
        "patients": query("SELECT * FROM patients ORDER BY id DESC"),
        "pills": query("SELECT * FROM pills ORDER BY id"),
        "rooms": query("SELECT * FROM rooms ORDER BY id")
    })

# ---- API: add queue ----
@app.post("/api/queues")
def api_add_queue():
    data = request.get_json(force=True)
    patient_id = int(data["patient_id"])
    pill_id = int(data["pill_id"])

    pill = query("SELECT * FROM pills WHERE id=?", (pill_id,))
    if not pill: return jsonify({"error":"pill not found"}), 400
    pill_type = pill[0]["type"]

    # routing rule: liquid -> room 3; solid -> R1 or R2 (round-robin by count)
    target_room = 3 if pill_type == "liquid" else _pick_solid_room()

    qid = execute(
        "INSERT INTO queues(patient_id,pill_id,target_room,status) VALUES(?,?,?,?)",
        (patient_id, pill_id, target_room, "pending")
    )
    execute("INSERT INTO events(queue_id, event, message) VALUES(?,?,?)",
            (qid, "created", json.dumps(data)))

    # publish mqtt command
    client = get_client()
    payload = {"queue_id": qid, "patient_id": patient_id, "pill_id": pill_id, "target_room": target_room}
    client.publish(MQTT_TOPIC_CMD, json.dumps(payload), qos=1, retain=False)
    execute("UPDATE queues SET status='sent' WHERE id=?", (qid,))
    return jsonify({"queue_id": qid, "target_room": target_room})

def _pick_solid_room():
    r1 = query("SELECT COUNT(*) cnt FROM queues WHERE target_room=1")[0]["cnt"]
    r2 = query("SELECT COUNT(*) cnt FROM queues WHERE target_room=2")[0]["cnt"]
    return 1 if r1 <= r2 else 2

# ---- API: CRUD (simple examples) ----
@app.post("/api/patients")
def add_patient():
    d = request.get_json(force=True)
    pid = execute("INSERT INTO patients(name,note) VALUES(?,?)", (d["name"], d.get("note")))
    return jsonify({"id": pid})

@app.delete("/api/queues/<int:qid>")
def del_queue(qid):
    execute("DELETE FROM queues WHERE id=?", (qid,))
    return jsonify({"ok": True})

if __name__ == "__main__":
    init_db()
    get_client()
    app.run(host=FLASK_HOST, port=FLASK_PORT)
