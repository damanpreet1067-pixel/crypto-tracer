from datetime import datetime
import networkx as nx
from chains.common import norm
from analytics.aml_labels import get_label

CLUSTER_COLORS = ["#84cc16", "#06b6d4", "#0f172a", "#92400e", "#4338ca"]
WINDOW_SECONDS = 600   # 10 minutes
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"

def _time(text):
    return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")


def short(addr):
    return addr[:8] + "..." + addr[-4:]


def find_clusters(center, txs, window=WINDOW_SECONDS):
    """Group counterparties that look related. Uses saved data only."""
    center = norm(center)

    own = get_label(center)
    if own and own["category"] in ("exchange", "mixer"):
        return {"skipped": f"Clustering skipped: this wallet is a known "
                           f"{own['category']} that serves many unrelated users.",
                "clusters": [], "round_trip": []}

    events = []   # (time, direction, token, other wallet)
    for t in txs:
        if not t["value"] or t["value"] <= 0 or not t["from"] or not t["to"]:
            continue
        if t["from"] == center:
            other, direction = t["to"], "out"
        elif t["to"] == center:
            other, direction = t["from"], "in"
        else:
            continue
        if other == center or get_label(other) or   other == ZERO_ADDRESS:
            continue   # skip itself, labeled services and the zero address
        events.append((_time(t["timestamp_utc"]), direction, t["token"], other))

    # ---- Batch groups: link wallets that appear close together in time ----
    G = nx.Graph()
    groups = {}
    for ev in events:
        groups.setdefault((ev[1], ev[2]), []).append(ev)

    for (direction, token), evs in groups.items():
        evs.sort()
        for i, a in enumerate(evs):
            for b in evs[i + 1:]:
                if (b[0] - a[0]).total_seconds() > window:
                    break
                if a[3] != b[3]:
                    G.add_edge(a[3], b[3], direction=direction)

    components = sorted(nx.connected_components(G), key=len, reverse=True)[:5]
    clusters = []
    for i, comp in enumerate(components, start=1):
        directions = {d["direction"] for _, _, d in G.subgraph(comp).edges(data=True)}
        if directions == {"out"}:
            how = "all received funds from this wallet within 10 minutes of each other"
        elif directions == {"in"}:
            how = "all sent funds to this wallet within 10 minutes of each other"
        else:
            how = "sent to or received from this wallet within 10 minutes of each other"
        members = sorted(comp)
        clusters.append({
            "id": i,
            "color": CLUSTER_COLORS[i - 1],
            "size": len(members),
            "reason": how,
            "members": [{"address": m, "short": short(m)} for m in members],
        })

    # ---- Round-trip wallets ----
    senders = {e[3] for e in events if e[1] == "in"}
    receivers = {e[3] for e in events if e[1] == "out"}
    round_trip = [{"address": a, "short": short(a)}
                  for a in sorted(senders & receivers)]

    return {"skipped": None, "clusters": clusters, "round_trip": round_trip}


def color_graph(graph, result):
    """Give cluster members a colored border and a [C1] tag in the graph."""
    member_to_cluster = {}
    for c in result["clusters"]:
        for m in c["members"]:
            member_to_cluster[m["address"]] = c

    for node in graph["nodes"]:
        c = member_to_cluster.get(node["id"])
        if c:
            node["color"] = {"background": node["color"], "border": c["color"]}
            node["borderWidth"] = 5
            node["label"] = f"{node['label']}\n[C{c['id']}]"
    return graph