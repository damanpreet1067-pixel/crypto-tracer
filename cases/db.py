import sqlite3
from chains.common import norm

DB_PATH = "data/tracer.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_cases():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS case_nodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER NOT NULL,
            address TEXT NOT NULL,
            chain TEXT NOT NULL,
            kind TEXT,
            label TEXT,
            note TEXT,
            added_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (case_id, address, chain)
        )
    """)
    conn.commit()
    conn.close()


def create_case(user_id, name):
    conn = get_conn()
    conn.execute("INSERT INTO cases (user_id, name) VALUES (?, ?)", (user_id, name))
    conn.commit()
    conn.close()


def list_cases(user_id):
    conn = get_conn()
    rows = conn.execute("""
        SELECT c.id, c.name, c.created_at, COUNT(n.id) AS node_count
        FROM cases c LEFT JOIN case_nodes n ON n.case_id = c.id
        WHERE c.user_id = ?
        GROUP BY c.id
        ORDER BY c.id DESC
    """, (user_id,)).fetchall()
    conn.close()
    return rows


def get_case(case_id, user_id):
    """Returns the case only if it belongs to this user."""
    conn = get_conn()
    row = conn.execute("SELECT * FROM cases WHERE id = ? AND user_id = ?",
                       (case_id, user_id)).fetchone()
    conn.close()
    return row


def get_case_nodes(case_id):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM case_nodes WHERE case_id = ? ORDER BY id",
                        (case_id,)).fetchall()
    conn.close()
    return rows


def add_node(case_id, address, chain, kind, label, note):
    """Returns 1 if added, 0 if it was already in the case."""
    conn = get_conn()
    cur = conn.execute("""
        INSERT OR IGNORE INTO case_nodes (case_id, address, chain, kind, label, note)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (case_id, norm(address), chain, kind, label, note))
    conn.commit()
    added = cur.rowcount
    conn.close()
    return added


def remove_node(case_id, node_id):
    conn = get_conn()
    conn.execute("DELETE FROM case_nodes WHERE id = ? AND case_id = ?",
                 (node_id, case_id))
    conn.commit()
    conn.close()