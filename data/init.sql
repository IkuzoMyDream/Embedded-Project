PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS patients(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  note TEXT
);

CREATE TABLE IF NOT EXISTS pills(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  type TEXT NOT NULL CHECK(type IN ('solid','liquid'))
);

CREATE TABLE IF NOT EXISTS rooms(
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS queues(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  patient_id INTEGER NOT NULL,
  pill_id INTEGER NOT NULL,
  target_room INTEGER NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending', -- pending|sent|success|failed
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  served_at DATETIME,
  FOREIGN KEY(patient_id) REFERENCES patients(id),
  FOREIGN KEY(pill_id) REFERENCES pills(id),
  FOREIGN KEY(target_room) REFERENCES rooms(id)
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
INSERT OR IGNORE INTO rooms(id,name) VALUES (1,'R1 solid'),(2,'R2 solid'),(3,'R3 liquid');
INSERT OR IGNORE INTO pills(id,name,type) VALUES
(1,'Solid A','solid'),(2,'Solid B','solid'),(3,'Solid C','solid'),(4,'Solid D','solid'),
(5,'Water Syrup','liquid');
