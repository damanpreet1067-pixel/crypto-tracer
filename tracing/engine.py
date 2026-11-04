import time

from analytics.aml_labels import get_label
from cache.db import get_conn, get_transactions_cached
from chains.common import norm
from chains.registry import CHAINS

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

# ---- Limits (raise them if you have the API quota and patience) ----
MAX_HOPS = 3
MAX_BREADTH = 5
MAX_NEW_DOWNLOADS = 15    # wallets fetched from an API in one trace
MAX_EXPLORED = 60         # wallets explored in total, cache included
TIME_BUDGET = 150         # seconds
MAX_PATHS = 5

STOP_CATEGORIES = ("exchange", "mixer", "sanctioned", "scam")
HOP_COLORS = ["#fb923c", "#38bdf8", "#818cf8", "#c084fc"]
CATEGORY_COLORS = {
    "exchange": "#facc15", "mixer": "#ef4444",
    "sanctioned": "#991b1b", "scam": "#ec4899",
}


def short(addr):
    return addr[:8] + "..." + addr[-4:] if len(addr) > 14 else addr


def name_of(addr):
    lab = get_label(addr)
    return lab["name"] if lab else short(addr)


def money(value):
    return f"{value:,.2f}" if value >= 1000 else f"{value:.6g}"


def is_cached(wallet, chain):
    """True if this wallet was already downloaded (so loading it is free)."""
    try:
        conn = get_conn()
        row = conn.execute(
            "SELECT 1 FROM addresses WHERE address = ? AND chain = ?",
            (wallet, chain)).fetchone()
        conn.close()
        return bool(row)
    except Exception:
        return False


def outgoing(wallet, txs, token, not_before):
    """Transfers that left `wallet` in one token, grouped by receiver.
    Only transfers at or after `not_before` count (money must arrive first)."""
    groups = {}
    for t in txs:
        if t["from"] != wallet or t["token"] != token:
            continue
        to = t["to"]
        if not to or to == wallet or to == ZERO_ADDRESS:
            continue
        if not t["value"] or t["value"] <= 0:
            continue
        if not_before and t["timestamp_utc"] < not_before:
            continue
        g = groups.get(to)
        if g is None:
            g = groups[to] = {"to": to, "total": 0.0, "count": 0,
                              "first": t["timestamp_utc"], "last": t["timestamp_utc"]}
        g["total"] += t["value"]
        g["count"] += 1
        g["first"] = min(g["first"], t["timestamp_utc"])
        g["last"] = max(g["last"], t["timestamp_utc"])
    return groups


def pick(groups, breadth, destination):
    """The biggest receivers, plus the destination if it is among them."""
    total = sum(g["total"] for g in groups.values()) or 1
    chosen = sorted(groups.values(), key=lambda g: g["total"], reverse=True)[:breadth]
    if destination and destination in groups and groups[destination] not in chosen:
        chosen.append(groups[destination])
    for g in chosen:
        g["share"] = g["total"] / total
    return chosen


def make_edge(wallet, g, token, hop):
    return {
        "from": wallet, "to": g["to"], "token": token,
        "total": g["total"], "count": g["count"],
        "first": g["first"], "last": g["last"], "hop": hop,
        "amount_text": money(g["total"]),
        "from_name": name_of(wallet), "to_name": name_of(g["to"]),
    }


def route_text(source, path):
    return " → ".join([name_of(source)] + [e["to_name"] for e in path])


def build_graph(source, destination, edges, paths, hop_of):
    on_path = {(e["from"], e["to"], e["token"]) for p in paths for e in p}
    wallets = {source}
    for e in edges.values():
        wallets.add(e["from"])
        wallets.add(e["to"])

    nodes = []
    for w in wallets:
        lab = get_label(w)
        level = hop_of.get(w, 0)
        if w == source:
            color, size, role = "#fb923c", 28, "Start wallet"
        elif destination and w == destination:
            color, size, role = "#22c55e", 26, "Destination"
        elif lab and lab["category"] in CATEGORY_COLORS:
            color, size, role = CATEGORY_COLORS[lab["category"]], 22, lab["category"].title()
        else:
            color, size, role = HOP_COLORS[min(level, 3)], 16, f"Hop {level}"
        nodes.append({
            "id": w, "label": lab["name"] if lab else short(w),
            "title": f"{role}\n{w}", "shape": "dot",
            "size": size, "color": color, "level": level,
        })

    graph_edges = []
    for (f, t, token), e in edges.items():
        highlight = (f, t, token) in on_path
        label = f"{e['amount_text']} {token}" + (f" x{e['count']}" if e["count"] > 1 else "")
        graph_edges.append({
            "from": f, "to": t, "label": label, "arrows": "to",
            "width": 4 if highlight else 1,
            "color": "#16a34a" if highlight else "#a5b4fc",
            "title": f"{e['from_name']} → {e['to_name']}\n{e['count']} transfer(s)\n"
                     f"First: {e['first']} UTC\nLast: {e['last']} UTC",
        })
    return {"nodes": nodes, "edges": graph_edges}


def save_nodes_for(source, destination, paths, endpoints, ends):
    """The wallets worth saving into a case."""
    nodes = {}

    def put(addr, note):
        if addr in nodes:
            return
        lab = get_label(addr)
        kind = "exchange point" if lab and lab["category"] == "exchange" else "wallet"
        nodes[addr] = {"address": addr, "label": lab["name"] if lab else "",
                       "kind": kind, "note": note}

    put(source, "Start of wallet-to-wallet trace")
    if destination:
        for number, path in enumerate(paths, start=1):
            for e in path:
                put(e["to"], f"Path {number}, hop {e['hop']} of a trace from {short(source)}")
    else:
        for x in endpoints:
            put(x["address"], f"{x['category'].title()} reached at hop {x['hop']} "
                              f"({x['token']}) from {short(source)}")
        for x in ends[:10]:
            put(x["address"], f"Trail continues from here (hop {x['hop']}, {x['token']})")
    return list(nodes.values())


def trace(chain, source, destination, hops, breadth):
    info = CHAINS[chain]
    source = norm(source)
    destination = norm(destination) if destination else None
    hops = max(1, min(int(hops), MAX_HOPS))
    breadth = max(1, min(int(breadth), MAX_BREADTH))

    started = time.time()
    loaded = {}
    stats = {"api": 0, "cache": 0}
    errors = []
    stopped = None

    def load(wallet):
        if wallet not in loaded:
            txs, src = get_transactions_cached(wallet, chain, info["fetch"], limit=50)
            loaded[wallet] = txs
            stats["api" if src == "API" else "cache"] += 1
        return loaded[wallet]

    def budget_problem(wallet):
        if wallet in loaded:
            return None
        if time.time() - started > TIME_BUDGET:
            return f"the {TIME_BUDGET}-second time limit was reached"
        if len(loaded) >= MAX_EXPLORED:
            return f"the limit of {MAX_EXPLORED} explored wallets was reached"
        if stats["api"] >= MAX_NEW_DOWNLOADS and not is_cached(wallet, chain):
            return f"the limit of {MAX_NEW_DOWNLOADS} new wallet downloads was reached"
        return None

    # The start wallet must load, so a failure here is shown to the user
    first_txs = load(source)
    tokens = sorted({t["token"] for t in first_txs
                     if t["from"] == source and t["value"] and t["value"] > 0})
    frontier = [{"wallet": source, "token": tk, "arrived": None, "path": [], "share": 1.0}
                for tk in tokens]

    edges = {}
    paths, endpoints, ends, stops = [], [], [], []
    expanded = set()
    hop_of = {source: 0}

    for hop in range(1, hops + 1):
        next_frontier = []
        for item in frontier:
            wallet, token = item["wallet"], item["token"]
            if (wallet, token) in expanded:
                continue
            expanded.add((wallet, token))

            problem = budget_problem(wallet)
            if problem:
                stopped = problem
                break
            try:
                txs = load(wallet)
            except Exception as e:
                errors.append({"address": wallet, "message": str(e)})
                continue

            groups = outgoing(wallet, txs, token, item["arrived"])
            if not groups:
                stops.append({"address": wallet, "name": name_of(wallet),
                              "token": token, "hop": hop - 1})
                continue

            on_path = {e["from"] for e in item["path"]} | {wallet}
            for g in pick(groups, breadth, destination):
                target = g["to"]
                if target in on_path:
                    continue
                edge = make_edge(wallet, g, token, hop)
                edges.setdefault((wallet, target, token), edge)
                hop_of.setdefault(target, hop)
                new_path = item["path"] + [edge]

                if destination and target == destination:
                    if len(paths) < MAX_PATHS:
                        paths.append(new_path)
                    continue

                label = get_label(target)
                if label and label["category"] in STOP_CATEGORIES:
                    endpoints.append({
                        "address": target, "name": label["name"],
                        "category": label["category"], "hop": hop, "token": token,
                        "route": route_text(source, new_path)})
                    continue

                if hop < hops:
                    next_frontier.append({"wallet": target, "token": token,
                                          "arrived": g["first"], "path": new_path,
                                          "share": g["share"]})
                else:
                    ends.append({"address": target, "name": name_of(target),
                                 "token": token, "hop": hop, "total": g["total"],
                                 "route": route_text(source, new_path)})
        if stopped:
            break
        if destination and paths:
            break
        next_frontier.sort(key=lambda f: f["share"], reverse=True)
        frontier = next_frontier

    own = get_label(source)
    source_note = None
    if own and own["category"] in ("exchange", "mixer"):
        source_note = (f"The start wallet is a known {own['category']} ({own['name']}). "
                       "Its transfers belong to many unrelated customers, so the paths "
                       "below are not meaningful. Start from a wallet used by one person or group.")

    return {
        "chain": chain, "chain_name": info["name"],
        "source": source, "destination": destination,
        "hops": hops, "breadth": breadth,
        "paths": paths, "endpoints": endpoints, "ends": ends, "stops": stops,
        "edges": sorted(edges.values(), key=lambda e: (e["hop"], -e["total"])),
        "graph": build_graph(source, destination, edges, paths, hop_of),
        "save_nodes": save_nodes_for(source, destination, paths, endpoints, ends),
        "wallets_explored": len(loaded),
        "api": stats["api"], "cache": stats["cache"],
        "seconds": round(time.time() - started, 1),
        "stopped": stopped, "errors": errors,
        "source_note": source_note, "no_outgoing": not tokens,
    }