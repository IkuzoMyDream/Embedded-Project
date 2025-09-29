import sqlite3
from contextlib import closing
from .config import DB_PATH, INIT_SQL

def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with open(INIT_SQL, "r", encoding="utf-8") as f, closing(get_conn()) as conn:
        conn.executescript(f.read())
        # lightweight migration: ensure 'note' column exists in queues (older DBs)
        try:
            cur = conn.execute("PRAGMA table_info(queues)")
            cols = [r[1] for r in cur.fetchall()]
            if 'note' not in cols:
                conn.execute("ALTER TABLE queues ADD COLUMN note TEXT")
        except Exception:
            pass
        conn.commit()

def query(sql, params=()):
    with closing(get_conn()) as conn:
        cur = conn.execute(sql, params)
        # normalize column names to lowercase to avoid case-sensitivity issues
        rows = []
        for r in cur.fetchall():
            d = dict(r)
            rows.append({k.lower(): v for k, v in d.items()})
    return rows

def execute(sql, params=()):
    with closing(get_conn()) as conn:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.lastrowid
