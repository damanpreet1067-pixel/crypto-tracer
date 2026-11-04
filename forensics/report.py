import os
import matplotlib
matplotlib.use("Agg")   # draw without opening a window
import matplotlib.pyplot as plt
import networkx as nx

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                Table, TableStyle, Image, PageBreak)

from forensics.export import (get_timeline, list_evidence, _new_path,
                              _register, utc_now)
from analytics.risk_score import calculate_risk
from analytics.aml_labels import get_label

CATEGORY_COLORS = {
    "exchange": "#facc15",
    "mixer": "#ef4444",
    "sanctioned": "#991b1b",
    "scam": "#ec4899",
}


def short(addr):
    return addr[:8] + "..." + addr[-4:] if addr else "-"


def make_graph_png(case_id, timeline, case_addresses):
    """Draw a wallet-to-wallet graph of the case and save it as PNG."""
    G = nx.DiGraph()
    for r in timeline[-60:]:          # the 60 newest transactions
        if r["from_addr"] and r["to_addr"]:
            G.add_edge(r["from_addr"], r["to_addr"])
    if G.number_of_nodes() == 0:
        return None

    node_colors = []
    labels = {}
    for n in G.nodes:
        lab = get_label(n)
        if n in case_addresses:
            node_colors.append("#fb923c")           # case wallet = orange
        elif lab:
            node_colors.append(CATEGORY_COLORS.get(lab["category"], "#facc15"))
        else:
            node_colors.append("#38bdf8")           # other = blue
        labels[n] = lab["name"] if lab else short(n)

    fig = plt.figure(figsize=(9, 6))
    pos = nx.spring_layout(G, seed=7, k=0.9)
    nx.draw_networkx(G, pos, node_color=node_colors, labels=labels,
                     font_size=6, node_size=320, arrows=True,
                     edge_color="#94a3b8", width=0.8)
    plt.title("Money flow (newest 60 transactions)", fontsize=10)
    plt.axis("off")

    path = _new_path(case_id, "graph", "png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    _register(case_id, path)
    return path


def risk_rows(nodes, timeline):
    """One risk result per wallet in the case, using saved data only."""
    rows = []
    for n in nodes:
        if n["kind"] != "wallet":
            continue
        addr = n["address"]
        txs = [{"from": r["from_addr"], "to": r["to_addr"]}
               for r in timeline
               if r["from_addr"] == addr or r["to_addr"] == addr]
        rows.append((addr, n["label"], calculate_risk(addr, txs)))
    return rows


def export_pdf(case, nodes):
    case_id = case["id"]
    timeline = get_timeline(nodes)
    case_addresses = {n["address"] for n in nodes if n["kind"] == "wallet"}
    graph_path = make_graph_png(case_id, timeline, case_addresses)

    styles = getSampleStyleSheet()
    cell = ParagraphStyle("cell", parent=styles["Normal"], fontSize=7, leading=9)
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=8, leading=10)

    path = _new_path(case_id, "report", "pdf")
    doc = SimpleDocTemplate(path, pagesize=A4, leftMargin=1.5 * cm,
                            rightMargin=1.5 * cm, topMargin=1.5 * cm,
                            bottomMargin=1.5 * cm)
    story = []

    # ---- 1. Title and summary ----
    story.append(Paragraph("Crypto Transaction Evidence Report", styles["Title"]))
    story.append(Paragraph(f"<b>Case:</b> {case['name']}", styles["Normal"]))
    story.append(Paragraph(f"<b>Case created (UTC):</b> {case['created_at']}", styles["Normal"]))
    story.append(Paragraph(f"<b>Report generated (UTC):</b> {utc_now()}", styles["Normal"]))
    exchange_points = sum(1 for n in nodes if n["kind"] == "exchange point")
    story.append(Paragraph(
        f"<b>Wallets:</b> {len(case_addresses)} &nbsp; "
        f"<b>Exchange points:</b> {exchange_points} &nbsp; "
        f"<b>Transactions in timeline:</b> {len(timeline)}", styles["Normal"]))
    story.append(Spacer(1, 12))

    # ---- 2. Case nodes ----
    story.append(Paragraph("Case nodes", styles["Heading2"]))
    data = [["Type", "Label", "Address", "Chain"]]
    for n in nodes:
        data.append([Paragraph(n["kind"], cell), Paragraph(n["label"] or "-", cell),
                     Paragraph(n["address"], cell), n["chain"]])
    t = Table(data, colWidths=[2.8 * cm, 3.5 * cm, 9 * cm, 2.2 * cm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t)
    story.append(Spacer(1, 12))

    # ---- 3. Risk scores ----
    story.append(Paragraph("Risk scores", styles["Heading2"]))
    data = [["Wallet", "Score", "Level", "Reasons"]]
    for addr, label, risk in risk_rows(nodes, timeline):
        data.append([Paragraph(label or short(addr), cell),
                     f"{risk['score']}/100", risk["level"],
                     Paragraph("; ".join(risk["reasons"]), cell)])
    t = Table(data, colWidths=[3.5 * cm, 1.8 * cm, 1.8 * cm, 10.4 * cm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t)
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Risk scores are indicators based on a small list of labeled addresses. "
        "They are not proof of wrongdoing.", small))

    # ---- 4. Graph ----
    if graph_path:
        story.append(PageBreak())
        story.append(Paragraph("Money flow graph", styles["Heading2"]))
        story.append(Image(graph_path, width=17 * cm, height=11.3 * cm))
        story.append(Paragraph(
            "Orange = case wallet, Blue = other wallet, Yellow = exchange, "
            "Red = mixer, Dark red = sanctioned, Pink = scam.", small))

    # ---- 5. Timeline ----
    story.append(PageBreak())
    story.append(Paragraph("UTC timeline", styles["Heading2"]))
    data = [["Time (UTC)", "From", "To", "Amount", "Token", "Tx hash"]]
    for r in timeline[:60]:
        data.append([r["timestamp_utc"],
                     Paragraph(r["from_label"] or short(r["from_addr"]), cell),
                     Paragraph(r["to_label"] or short(r["to_addr"]), cell),
                     f"{r['value']:.6g}", r["token"],
                     Paragraph(r["hash"][:16] + "...", cell)])
    t = Table(data, colWidths=[3.2 * cm, 3.3 * cm, 3.3 * cm, 2.2 * cm, 1.5 * cm, 4 * cm],
              repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 7),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t)
    if len(timeline) > 60:
        story.append(Paragraph(
            f"Showing the first 60 of {len(timeline)} transactions. "
            "The CSV and JSON exports contain all of them.", small))

    # ---- 6. Hash log ----
    story.append(Spacer(1, 14))
    story.append(Paragraph("Integrity: SHA-256 of exported files", styles["Heading2"]))
    files = list_evidence(case_id)
    if files:
        data = [["File", "SHA-256", "Created (UTC)"]]
        for f in files:
            data.append([Paragraph(f["filename"], cell),
                         Paragraph(f["sha256"], cell), f["created_utc"]])
        t = Table(data, colWidths=[5 * cm, 8.5 * cm, 3.5 * cm], repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(t)
    else:
        story.append(Paragraph("No files had been exported before this report.", small))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "The hash of this PDF is recorded in the case's Evidence page after generation. "
        "To verify a file, compute its SHA-256 and compare it with the log.", small))

    doc.build(story)
    _register(case_id, path)
    return path