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
        conn.commit()

def query(sql, params=()):
    with closing(get_conn()) as conn:
        cur = conn.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]
    return rows

def execute(sql, params=()):
    with closing(get_conn()) as conn:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.lastrowid
