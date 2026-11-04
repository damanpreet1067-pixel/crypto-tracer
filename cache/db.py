import sqlite3
import os
from chains.common import norm
from datetime import datetime, timezone

DB_PATH = "data/tracer.db"
os.makedirs("data", exist_ok=True)


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_cache():
    """Create the tables if they don't exist yet."""
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS addresses (
            address TEXT NOT NULL,
            chain TEXT NOT NULL,
            fetched_at TEXT,
            PRIMARY KEY (address, chain)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            chain TEXT NOT NULL,
            hash TEXT NOT NULL,
            from_addr TEXT,
            to_addr TEXT,
            value REAL,
            token TEXT DEFAULT 'ETH',
            timestamp_utc TEXT,
            block INTEGER,
            PRIMARY KEY (chain, hash, token, from_addr, to_addr, value)
        )
    """)
    conn.commit()
    conn.close()


def get_transactions_cached(address, chain, fetch_function, limit=50):
    """
    Look in SQLite first. Only call the API if we've never seen this wallet.
    Returns (transactions, source) where source is "CACHE" or "API".
    """
    address = norm(address)
    init_cache()
    conn = get_conn()

    seen = conn.execute(
        "SELECT 1 FROM addresses WHERE address = ? AND chain = ?",
        (address, chain),
    ).fetchone()

    # ---- Already saved: read from our own database ----
    if seen:
        rows = conn.execute("""
            SELECT * FROM transactions
            WHERE chain = ? AND (from_addr = ? OR to_addr = ?)
            ORDER BY timestamp_utc DESC
            LIMIT ?
        """, (chain, address, address, limit * 3)).fetchall()
        conn.close()
        txs = [{
            "hash": r["hash"],
            "from": r["from_addr"],
            "to": r["to_addr"],
            "value": r["value"],
            "token": r["token"],
            "timestamp_utc": r["timestamp_utc"],
            "block": r["block"],
        } for r in rows]
        return txs, "CACHE"

    # ---- First time: call the API, then save the result ----
    txs = fetch_function(address, limit)

    for t in txs:
        conn.execute("""
            INSERT OR IGNORE INTO transactions
            (chain, hash, from_addr, to_addr, value, token, timestamp_utc, block)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (chain, t["hash"], t["from"], t["to"], t["value"],
              t["token"], t["timestamp_utc"], t["block"]))

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT OR REPLACE INTO addresses (address, chain, fetched_at) VALUES (?, ?, ?)",
        (address, chain, now),
    )
    conn.commit()
    conn.close()
    return txs, "API"