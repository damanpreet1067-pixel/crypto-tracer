import networkx as nx
from datetime import datetime, timezone
from chains.common import norm

TOKEN_COLORS = {
    "ETH": "#475569",    # grey
    "USDT": "#16a34a",   # green
    "USDC": "#7c3aed",   # purple
    "BTC": "#d97706",    # orange-brown
    "TRX": "#0d9488",    # teal
    "BNB": "#a16207",    # dark gold
}


def build_graph(center_address, txs):
    """Build a NetworkX graph: Wallet -> Transaction -> Wallet."""
    G = nx.MultiDiGraph()
    center = norm(center_address)
    now = datetime.now(timezone.utc)

    for i, t in enumerate(txs):
        sender = t["from"]
        receiver = t["to"]
        if not sender or not receiver:
            continue  # skip contract creations (no receiver)

        when = datetime.strptime(t["timestamp_utc"], "%Y-%m-%d %H:%M:%S")
        when = when.replace(tzinfo=timezone.utc)
        age_days = (now - when).days

        for w in (sender, receiver):
            if w not in G:
                G.add_node(w, kind="wallet")

        # Unique id, because one hash can hold several transfers
        tx_id = f"{t['hash']}|{t['token']}|{i}"
        G.add_node(tx_id, kind="tx", hash=t["hash"], value=t["value"],
                   token=t["token"], time=t["timestamp_utc"], age_days=age_days)

        G.add_edge(sender, tx_id)
        G.add_edge(tx_id, receiver)

    return graph_to_json(G, center)


def graph_to_json(G, center):
    """Convert the NetworkX graph into the format the browser needs."""
    nodes = []
    for node, info in G.nodes(data=True):
        if info["kind"] == "wallet":
            is_center = (node == center)
            nodes.append({
                "id": node,
                "label": node[:6] + "..." + node[-4:],
                "title": node,
                "shape": "dot",
                "size": 28 if is_center else 16,
                "color": "#fb923c" if is_center else "#38bdf8",
            })
        else:
            nodes.append({
                "id": node,
                "label": f"{info['value']:.4g} {info['token']}\n{info['age_days']}d ago",
                "title": f"Tx: {info['hash']}\nToken: {info['token']}\n"
                         f"Time (UTC): {info['time']}\nAge: {info['age_days']} days",
                "shape": "box",
                "font": {"size": 11, "color": "#ffffff"},
                "color": TOKEN_COLORS.get(info["token"], "#475569"),
            })

    edges = [{"from": u, "to": v, "arrows": "to"} for u, v in G.edges()]

    return {
        "nodes": nodes,
        "edges": edges,
        "wallet_count": sum(1 for _, d in G.nodes(data=True) if d["kind"] == "wallet"),
        "tx_count": sum(1 for _, d in G.nodes(data=True) if d["kind"] == "tx"),
    }