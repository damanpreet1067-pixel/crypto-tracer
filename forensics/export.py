import csv
import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone

from cases.db import get_conn
from analytics.aml_labels import get_label

EXPORT_DIR = "exports"
os.makedirs(EXPORT_DIR, exist_ok=True)


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def init_evidence():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS evidence_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            created_utc TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def sha256_of_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def list_evidence(case_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM evidence_files WHERE case_id = ? ORDER BY id DESC",
        (case_id,)).fetchall()
    conn.close()
    return rows


def get_timeline(nodes):
    """All saved transactions of the case wallets, oldest first (UTC).
    Reads only from SQLite, so it never calls the API."""
    rows = []
    seen = set()
    conn = get_conn()
    try:
        for n in nodes:
            if n["kind"] != "wallet":
                continue
            found = conn.execute("""
                SELECT * FROM transactions
                WHERE chain = ? AND (from_addr = ? OR to_addr = ?)
            """, (n["chain"], n["address"], n["address"])).fetchall()
            for r in found:
                key = (r["hash"], r["token"], r["from_addr"], r["to_addr"], r["value"])
                if key in seen:
                    continue
                seen.add(key)
                d = dict(r)
                f = get_label(d["from_addr"])
                t = get_label(d["to_addr"])
                d["from_label"] = f["name"] if f else ""
                d["to_label"] = t["name"] if t else ""
                rows.append(d)
    except sqlite3.OperationalError:
        pass  # transactions table doesn't exist yet
    finally:
        conn.close()

    rows.sort(key=lambda r: r["timestamp_utc"])
    return rows


def _new_path(case_id, name, ext):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return os.path.join(EXPORT_DIR, f"case{case_id}_{name}_{stamp}.{ext}")


def _register(case_id, path):
    """Hash the finished file and save the hash in the database."""
    digest = sha256_of_file(path)
    conn = get_conn()
    conn.execute("""
        INSERT INTO evidence_files (case_id, filename, sha256, created_utc)
        VALUES (?, ?, ?, ?)
    """, (case_id, os.path.basename(path), digest, utc_now()))
    conn.commit()
    conn.close()
    return digest


def export_nodes_csv(case, nodes):
    path = _new_path(case["id"], "nodes", "csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["type", "label", "address", "chain", "note", "added_utc"])
        for n in nodes:
            w.writerow([n["kind"], n["label"], n["address"], n["chain"],
                        n["note"], n["added_at"]])
    _register(case["id"], path)
    return path


def export_timeline_csv(case, nodes):
    path = _new_path(case["id"], "timeline", "csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["timestamp_utc", "chain", "token", "value", "from",
                    "from_label", "to", "to_label", "tx_hash", "block"])
        for r in get_timeline(nodes):
            w.writerow([r["timestamp_utc"], r["chain"], r["token"], r["value"],
                        r["from_addr"], r["from_label"], r["to_addr"],
                        r["to_label"], r["hash"], r["block"]])
    _register(case["id"], path)
    return path


def export_json(case, nodes):
    path = _new_path(case["id"], "full", "json")
    data = {
        "case": {"id": case["id"], "name": case["name"],
                 "created_utc": case["created_at"]},
        "exported_utc": utc_now(),
        "nodes": [{"type": n["kind"], "label": n["label"],
                   "address": n["address"], "chain": n["chain"],
                   "note": n["note"], "added_utc": n["added_at"]}
                  for n in nodes],
        "timeline": get_timeline(nodes),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    _register(case["id"], path)
    return path