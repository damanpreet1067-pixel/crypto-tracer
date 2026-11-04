import importlib
import json
import os
import sqlite3

print("=== Files ===")
files = [
    "app.py", "config.py", "data/labels.json",
    "chains/ethereum.py", "chains/bitcoin.py", "chains/tron.py", "chains/bsc.py",
    "chains/registry.py", "chains/common.py", "chains/tokens.py",
    "cache/db.py", "cases/db.py", "graph/builder.py",
    "analytics/aml_labels.py", "analytics/risk_score.py",
    "analytics/behavior.py", "analytics/clustering.py",
    "forensics/export.py", "forensics/report.py", "forensics/routes.py",
    "templates/login.html", "templates/register.html", "templates/dashboard.html",
    "templates/cases.html", "templates/case.html", "templates/evidence.html",
]
for f in files:
    print("OK     " if os.path.exists(f) else "MISSING", f)

print("\n=== Modules import ===")
modules = [
    "chains.registry", "cache.db", "cases.db", "graph.builder",
    "analytics.risk_score", "analytics.behavior", "analytics.clustering",
    "forensics.export", "forensics.report", "forensics.routes",
]
for m in modules:
    try:
        importlib.import_module(m)
        print("OK     ", m)
    except Exception as e:
        print("BROKEN ", m, "->", e)

print("\n=== labels.json ===")
try:
    with open("data/labels.json", encoding="utf-8") as f:
        print("OK      valid JSON,", len(json.load(f)), "labels")
except Exception as e:
    print("BROKEN  ", e)

print("\n=== API keys (values are not shown) ===")
try:
    import config
    for name in ("ETHERSCAN_API_KEY", "TRONGRID_API_KEY", "MEGANODE_API_KEY"):
        value = getattr(config, name, "")
        status = "set" if value and "PASTE" not in value else "EMPTY"
        print(f"{status:7}", name)
except Exception as e:
    print("BROKEN  config.py ->", e)

print("\n=== Database tables ===")
try:
    conn = sqlite3.connect("data/tracer.db")
    found = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    for t in ("users", "addresses", "transactions", "cases", "case_nodes", "evidence_files"):
        print("OK     " if t in found else "not yet", t)
except Exception as e:
    print("BROKEN  ", e)