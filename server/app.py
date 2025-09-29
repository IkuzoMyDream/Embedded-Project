from flask import Flask, send_from_directory, request, jsonify, current_app
from flask_cors import CORS
import json
from .db import init_db, query, execute
from .config import FLASK_HOST, FLASK_PORT, MQTT_TOPIC_CMD
from . import mqtt_client
import os
import logging

# detect react build folder
build_static = os.path.join(os.path.dirname(__file__), '..', 'client', 'build', 'static')
if os.path.exists(build_static):
    static_folder = os.path.join(os.path.dirname(__file__), '..', 'client', 'build')
    static_url_path = ''
else:
    # during dev serve legacy static folder
    static_folder = os.path.join(os.path.dirname(__file__), '..', 'client', 'static')
    static_url_path = '/static'

app = Flask(__name__, static_folder=static_folder, static_url_path=static_url_path)
CORS(app)

# configure logging to show debug messages in console
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
app.logger.setLevel(logging.DEBUG)
# also set werkzeug logger to INFO or DEBUG if needed
logging.getLogger('werkzeug').setLevel(logging.INFO)

# ---- serve pages / react ----
@app.route('/')
def root():
    # if react build exists serve index.html from build
    build_index = os.path.join(app.static_folder, 'index.html')
    if os.path.exists(build_index):
        return send_from_directory(app.static_folder, 'index.html')
    # fallback to legacy pages
    return send_from_directory(os.path.join(os.path.dirname(__file__), '..', 'client', 'pages'), 'dashboard.html')

@app.route('/<path:filename>')
def serve_any(filename):
    # serve built static assets first
    if os.path.exists(os.path.join(app.static_folder, filename)):
        return send_from_directory(app.static_folder, filename)
    # serve legacy pages
    legacy_path = os.path.join(os.path.dirname(__file__), '..', 'client', 'pages')
    if os.path.exists(os.path.join(legacy_path, filename)):
        return send_from_directory(legacy_path, filename)
    # fallback to index for client-side routing
    build_index = os.path.join(app.static_folder, 'index.html')
    if os.path.exists(build_index):
        return send_from_directory(app.static_folder, 'index.html')
    return ('Not Found', 404)

# ---- API: basic reads ----
@app.get("/api/dashboard")
def api_dashboard():
    # fetch all pending/sent queues ordered by creation (to determine current and next)
    pending = query("""
      SELECT q.id AS queue_id, q.queue_number, p.name AS patient_name, r.name AS room, q.status
      FROM queues q
      JOIN patients p ON p.id=q.patient_id
      JOIN rooms r ON r.id=q.target_room
      WHERE q.status IN ('pending','sent','in_progress')
      ORDER BY q.created_at ASC
    """)

    # --- เพิ่มเติม: ดึง queue_items ของ pending ทั้งหมด ---
    pending_ids = [q['queue_id'] for q in pending]
    items_by_queue = {}
    if pending_ids:
        placeholders = ','.join(['?']*len(pending_ids))
        rows = query(f"""
            SELECT qi.queue_id, qi.pill_id, qi.quantity, p.name as pill_name
            FROM queue_items qi
            JOIN pills p ON p.id=qi.pill_id
            WHERE qi.queue_id IN ({placeholders})
        """, tuple(pending_ids))
        for row in rows:
            qid = row['queue_id']
            if qid not in items_by_queue:
                items_by_queue[qid] = []
            items_by_queue[qid].append({
                'pill_id': row['pill_id'],
                'name': row['pill_name'],
                'quantity': row['quantity']
            })
    # ใส่ items ให้แต่ละ pending
    for q in pending:
        q['items'] = items_by_queue.get(q['queue_id'], [])

    current = pending[0] if pending else None
    next_q = pending[1] if len(pending) > 1 else None

    # previous = most recent successful queue (last served)
    prev = query("""
      SELECT q.id AS queue_id, q.queue_number, p.name AS patient_name, r.name AS room, q.status
      FROM queues q
      JOIN patients p ON p.id=q.patient_id
      JOIN rooms r ON r.id=q.target_room
      WHERE q.status = 'success'
      ORDER BY q.created_at DESC LIMIT 1
    """)

    # currently processing queues
    processing = query("""
      SELECT q.id AS queue_id, q.queue_number, p.name AS patient_name, r.name AS room, q.status
      FROM queues q
      JOIN patients p ON p.id=q.patient_id
      JOIN rooms r ON r.id=q.target_room
      WHERE q.status IN ('processing','in_progress')
      ORDER BY q.created_at ASC
    """)

    # recent served (success) queues
    served = query("""
      SELECT q.id AS queue_id, q.queue_number, p.name AS patient_name, r.name AS room, q.status, q.served_at
      FROM queues q
      JOIN patients p ON p.id=q.patient_id
      JOIN rooms r ON r.id=q.target_room
      WHERE q.status = 'success'
      ORDER BY q.served_at DESC
      LIMIT 10
    """)

    # failed queues for monitoring (simplified query without new columns)
    failed = query("""
      SELECT q.id AS queue_id, q.queue_number, p.name AS patient_name, r.name AS room, 
             q.status, q.created_at
      FROM queues q
      JOIN patients p ON p.id=q.patient_id
      JOIN rooms r ON r.id=q.target_room
      WHERE q.status = 'failed'
      ORDER BY q.created_at DESC
      LIMIT 10
    """)

    logs = query("SELECT id, queue_id, ts, event, message FROM events ORDER BY id DESC LIMIT 50")
    success_count = query("SELECT COUNT(*) AS cnt FROM queues WHERE status='success'")[0]["cnt"]
    failed_count = query("SELECT COUNT(*) AS cnt FROM queues WHERE status='failed'")[0]["cnt"]
    return jsonify({
        "pending": pending,
        "processing": processing,
        "served": served,
        "failed": failed,
        "previous": prev[0] if prev else None,
        "current": current,
        "next": next_q,
        "logs": logs,
        "success_count": success_count,
        "failed_count": failed_count
    })

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
    # log raw body for debugging
    raw = request.get_data(as_text=True)
    try:
        data = request.get_json(force=True)
    except Exception as e:
        app.logger.exception('Failed to parse JSON for /api/queues: %s', e)
        return jsonify({"error": "invalid json"}), 400

    app.logger.debug('POST /api/queues raw body: %s', raw)
    app.logger.debug('POST /api/queues parsed json: %s', data)

    patient_id = data.get("patient_id")
    items = data.get("items", [])
    if not items:
        app.logger.warning('items required payload=%s', data)
        return jsonify({"error": "items required"}), 400

    # ensure patient_id is integer
    try:
        patient_id = int(patient_id)
    except Exception:
        return jsonify({"error": "invalid patient_id"}), 400

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
        # ลดจำนวนสต็อกยาในตาราง pills ตามจำนวนที่จ่าย (ไม่ให้ติดลบ)
        try:
            # log current amount
            before = query("SELECT amount FROM pills WHERE id=?", (it["pill_id"],))
            app.logger.debug('Pill %s before amount=%s', it.get('pill_id'), (before[0]["amount"] if before else None))

            execute(
                "UPDATE pills SET amount = MAX(0, amount - ?) WHERE id=?",
                (it["quantity"], it["pill_id"])
            )

            after = query("SELECT amount FROM pills WHERE id=?", (it["pill_id"],))
            app.logger.debug('Pill %s after amount=%s', it.get('pill_id'), (after[0]["amount"] if after else None))
        except Exception as e:
            app.logger.exception('Failed to update pill amount for pill_id=%s: %s', it.get('pill_id'), e)

    # event log
    # enrich items with pill name for event log (for all event types)
    def enrich_items(items):
        pill_ids = [int(x["pill_id"]) for x in items]
        pills = {p["id"]: p for p in query(
            f"SELECT id,name FROM pills WHERE id IN ({','.join(['?']*len(pill_ids))})",
            tuple(pill_ids)
        )}
        return [{"pill_id": it["pill_id"], "name": pills.get(it["pill_id"],{}).get("name"), "quantity": it["quantity"]} for it in items]

    execute("INSERT INTO events(queue_id, event, message) VALUES(?,?,?)",
            (qid, "created", json.dumps({"patient_id": patient_id, "items": enrich_items(norm_items)})))

    # Try to dispatch immediately if both nodes are ready
    try:
        client = mqtt_client.get_client()
        # Use centralized dispatch instead of per-node dispatch
        mqtt_client._dispatch_next_queue(client)
    except Exception as e:
        app.logger.exception('Failed to dispatch queue immediately: %s', e)

    # return queue_number และ updated pill amounts เพื่อให้ client อัปเดตสต็อกทันที
    qrow = query("SELECT queue_number FROM queues WHERE id=?", (qid,))

    # build list of pill ids from the normalized items (safer)
    try:
        updated_ids = [it['pill_id'] for it in norm_items]
        if updated_ids:
            placeholders = ','.join(['?'] * len(updated_ids))
            updated_pills = query(f"SELECT id, amount FROM pills WHERE id IN ({placeholders})", tuple(updated_ids))
        else:
            updated_pills = []
    except Exception as e:
        app.logger.exception('Failed to fetch updated_pills: %s', e)
        updated_pills = []
    app.logger.debug('Returning updated_pills: %s', updated_pills)

    return jsonify({"queue_id": qid, "queue_number": qrow[0]["queue_number"], "target_room": target_room, "updated_pills": updated_pills})

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

@app.post('/api/drugs')
def update_drugs():
    data = request.get_json(force=True)
    drugs = data.get('drugs', [])
    # ดึง id ทั้งหมดใน pills
    old_pills = query('SELECT id, name FROM pills')
    old_ids = {int(p['id']) for p in old_pills}
    new_ids = set()
    # อัปเดตหรือเพิ่มยาใหม่
    for d in drugs:
        pid = d.get('id')
        name = d.get('name') or ''
        type_ = (d.get('type') or '').strip().lower()
        if type_ not in ('solid', 'liquid'):
            type_ = 'solid'  # default ปลอดภัย
        amount = int(d.get('quantity') or 0)
        if pid is not None and str(pid).isdigit() and int(pid) in old_ids:
            # update ถ้ามี id เดิม
            execute('UPDATE pills SET name=?, type=?, amount=? WHERE id=?', (name, type_, amount, int(pid)))
            new_ids.add(int(pid))
        else:
            # insert ถ้าไม่มี id
            new_id = execute('INSERT INTO pills(name, type, amount) VALUES (?, ?, ?)', (name, type_, amount))
            new_ids.add(int(new_id))
    # ลบเฉพาะ id ที่ไม่มีใน drugs ใหม่
    for old in old_pills:
        if int(old['id']) not in new_ids:
            execute('DELETE FROM pills WHERE id=?', (int(old['id']),))
    return jsonify({'ok': True})


if __name__ == "__main__":
    init_db()
    mqtt_client.get_client()
    app.run(host=FLASK_HOST, port=FLASK_PORT)


