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
      SELECT q.id AS queue_id, q.queue_number, p.name AS patient_name, r.name AS room, q.status
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
        "patients": query("SELECT id,name,note FROM patients ORDER BY id DESC"),
        "pills": query("SELECT id,name,type,amount FROM pills ORDER BY id"),
        "rooms": query("SELECT id,name FROM rooms ORDER BY id")
    })


# ---- API: add queue (หลายยา) ----
@app.post("/api/queues")
def api_add_queue():
    """
    Expected JSON:
    {
      "patient_id": 1,
      "items": [
        {"pill_id": 2, "quantity": 10},
        {"pill_id": 5, "quantity": 1}  # ของเหลวจะถูกบังคับ = 1
      ]
    }
    """
    data = request.get_json(force=True)
    patient_id = int(data["patient_id"])
    items = data.get("items", [])
    if not items:
        return jsonify({"error": "items required"}), 400

    # Validate + normalize quantity (liquid = 1)
    pill_ids = [int(x["pill_id"]) for x in items]
    db_pills = {p["id"]: p for p in query(
        f"SELECT id,name,type,amount FROM pills WHERE id IN ({','.join(['?']*len(pill_ids))})",
        tuple(pill_ids)
    )}

    norm_items = []
    any_liquid = False
    for it in items:
        pid = int(it["pill_id"])
        pill = db_pills.get(pid)
        if not pill:
            return jsonify({"error": f"pill_id {pid} not found"}), 400
        q = int(it.get("quantity", 1))
        if pill["type"] == "liquid":
            q = 1  # fix ตาม requirement
            any_liquid = True
        if q <= 0:
            return jsonify({"error": f"quantity for pill {pid} must be > 0"}), 400
        norm_items.append({"pill_id": pid, "quantity": q, "type": pill["type"]})

    # routing rule: ถ้ามีของเหลว ส่งไปห้อง 3, ถ้าไม่มี เลือก R1/R2 แบบ balance
    target_room = 3 if any_liquid else _pick_solid_room()

    # สร้างคิว (header)
    qid = execute(
        "INSERT INTO queues(patient_id,target_room,status) VALUES(?,?,?)",
        (patient_id, target_room, "pending")
    )

    # แทรกรายการยา (items)
    for it in norm_items:
        execute(
            "INSERT INTO queue_items(queue_id,pill_id,quantity) VALUES(?,?,?)",
            (qid, it["pill_id"], it["quantity"])
        )

    # event log
    execute("INSERT INTO events(queue_id, event, message) VALUES(?,?,?)",
            (qid, "created", json.dumps({"patient_id": patient_id, "items": norm_items})))

    # publish mqtt command (ส่งทั้ง list ของยา)
    client = get_client()
    payload = {
        "queue_id": qid,
        "patient_id": patient_id,
        "target_room": target_room,
        "items": [{"pill_id": it["pill_id"], "quantity": it["quantity"]} for it in norm_items]
    }
    client.publish(MQTT_TOPIC_CMD, json.dumps(payload), qos=1, retain=False)
    execute("UPDATE queues SET status='sent' WHERE id=?", (qid,))

    # ส่งกลับ queue_number เพื่อใช้แสดงหน้าเว็บ
    qrow = query("SELECT queue_number FROM queues WHERE id=?", (qid,))
    return jsonify({"queue_id": qid, "queue_number": qrow[0]["queue_number"], "target_room": target_room})

def _pick_solid_room():
    r1 = query("SELECT COUNT(*) cnt FROM queues WHERE target_room=1")[0]["cnt"]
    r2 = query("SELECT COUNT(*) cnt FROM queues WHERE target_room=2")[0]["cnt"]
    return 1 if r1 <= r2 else 2

# ---- API: CRUD (ตัวอย่างเดิม) ----
@app.post("/api/patients")
def add_patient():
    d = request.get_json(force=True)
    pid = execute("INSERT INTO patients(name,note) VALUES(?,?)", (d["name"], d.get("note")))
    return jsonify({"id": pid})

@app.delete("/api/queues/<int:qid>")
def del_queue(qid):
    execute("DELETE FROM queues WHERE id=?", (qid,))
    return jsonify({"ok": True})

@app.get("/api/pills")
def list_pills():
    return jsonify(query("SELECT id,name,type,amount FROM pills ORDER BY id"))

@app.post("/api/pills")
def create_pill():
    d = request.get_json(force=True)
    pid = execute("INSERT INTO pills(name,amount,type) VALUES(?,?,?)",
                  (d["name"], int(d.get("amount",0)), d["type"]))
    return jsonify({"id": pid})

@app.patch("/api/pills/<int:pid>")
def patch_pill(pid):
    d = request.get_json(force=True)
    if "delta" in d:
      execute("UPDATE pills SET amount = MAX(0, amount + ?) WHERE id=?", (int(d["delta"]), pid))
    return jsonify({"ok": True})

@app.delete("/api/pills/<int:pid>")
def delete_pill(pid):
    execute("DELETE FROM pills WHERE id=?", (pid,))
    return jsonify({"ok": True})


if __name__ == "__main__":
    init_db()
    get_client()
    app.run(host=FLASK_HOST, port=FLASK_PORT)


