PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS patients(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  note TEXT
);

CREATE TABLE IF NOT EXISTS pills(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  amount INTEGER NOT NULL,
  type TEXT NOT NULL CHECK(type IN ('solid','liquid'))
);

CREATE TABLE IF NOT EXISTS rooms(
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL
);

-- Queue header (1 คน ต่อ 1 คิว)
CREATE TABLE IF NOT EXISTS queues(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  patient_id INTEGER NOT NULL,
  target_room INTEGER NOT NULL,
  queue_number TEXT GENERATED ALWAYS AS (printf('%03d',id)) VIRTUAL, -- เช่น id=1 → "001"
  status TEXT NOT NULL DEFAULT 'pending', -- pending|sent|success|failed
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  served_at DATETIME,
  FOREIGN KEY(patient_id) REFERENCES patients(id),
  FOREIGN KEY(target_room) REFERENCES rooms(id)
);

-- รายการยาในแต่ละคิว
CREATE TABLE IF NOT EXISTS queue_items(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  queue_id INTEGER NOT NULL,
  pill_id INTEGER NOT NULL,
  quantity INTEGER NOT NULL DEFAULT 1,
  FOREIGN KEY(queue_id) REFERENCES queues(id) ON DELETE CASCADE,
  FOREIGN KEY(pill_id) REFERENCES pills(id)
);

CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  queue_id INTEGER,
  ts DATETIME DEFAULT CURRENT_TIMESTAMP,
  event TEXT NOT NULL,
  message TEXT,
  FOREIGN KEY(queue_id) REFERENCES queues(id)
);

/* seed */
INSERT OR IGNORE INTO rooms(id,name) VALUES
 (1,'ห้องจ่ายยา 1'),
 (2,'ห้องจ่ายยา 2'),
 (3,'ห้องจ่ายยา 3');

-- 4 ยาเม็ด, 1 ยาน้ำ + ใส่ amount
INSERT OR IGNORE INTO pills(id,name,amount,type) VALUES
 (1,'ยาพาราเซตามอล 500มก', 150, 'solid'),       -- 150 เม็ด
 (2,'ยาแก้อักเสบ อะม็อกซิซิลลิน 500มก', 80, 'solid'),
 (3,'ยาลดน้ำตาลในเลือด เมทฟอร์มิน 500มก', 120, 'solid'),
 (4,'ยาลดไขมัน อะทอร์วาสแตติน 10มก', 60, 'solid'),
 (5,'ยาน้ำแก้ไอ', 2, 'liquid');                 -- 2 ลิตร

