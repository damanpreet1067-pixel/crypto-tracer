import sqlite3
import sys

from analytics.aml_labels import get_label
from chains.common import norm

START = norm(sys.argv[1]) if len(sys.argv) > 1 else "0xd8da6bf26964af9d7eed9e03e53415d37aa96045"
CHAIN = sys.argv[2] if len(sys.argv) > 2 else "ethereum"
ZERO = "0x0000000000000000000000000000000000000000"

conn = sqlite3.connect("data/tracer.db")
conn.row_factory = sqlite3.Row


def outgoing(wallet, arrival=None):
    """Who this wallet sent to, per token. Money must arrive before it is forwarded."""
    rows = conn.execute("""
        SELECT to_addr, token, value, timestamp_utc FROM transactions
        WHERE chain = ? AND from_addr = ? AND value > 0
          AND to_addr != ? AND to_addr != ?
    """, (CHAIN, wallet, wallet, ZERO)).fetchall()
    groups = {}
    for r in rows:
        if arrival is not None:
            if r["token"] not in arrival or r["timestamp_utc"] < arrival[r["token"]]:
                continue
        g = groups.setdefault((r["to_addr"], r["token"]),
                              {"to": r["to_addr"], "token": r["token"], "total": 0.0,
                               "count": 0, "first": r["timestamp_utc"]})
        g["total"] += r["value"]
        g["count"] += 1
        g["first"] = min(g["first"], r["timestamp_utc"])
    return sorted(groups.values(), key=lambda g: g["total"], reverse=True)


def line(i, g):
    lab = get_label(g["to"])
    name = f"  [{lab['name']}]" if lab else ""
    return f"  {i}. {g['to']}  |  {g['token']}  |  {g['total']:,.6g} total, {g['count']} transfer(s){name}"


hop1 = outgoing(START)
if not hop1:
    print("Nothing saved for this start wallet yet.")
    print("Run a trace for it on the Wallet Trace page first (Hops 2), then run this script again.")
    raise SystemExit

print(f"START ({CHAIN}):\n  {START}\n")
print("HOP 1 receivers (use as Destination with Hops = 1):")
for i, g in enumerate(hop1[:5], 1):
    print(line(i, g))

print("\nHOP 2 receivers (use as Destination with Hops = 2):")
found_hop2 = False
for g in hop1[:3]:
    arrival = {g["token"]: g["first"]}
    for h in outgoing(g["to"], arrival)[:3]:
        if h["to"] in (START, g["to"]):
            continue
        found_hop2 = True
        lab = get_label(h["to"])
        print(f"  via {g['to'][:10]}...{g['to'][-4:]} ({g['token']})")
        print(f"     {h['to']}  |  {h['token']}  |  {h['total']:,.6g} total, {h['count']} transfer(s)"
              + (f"  [{lab['name']}]" if lab else ""))
if not found_hop2:
    print("  None saved yet. Run a 2-hop trace on Wallet Trace first, then run this again.")
conn.close()