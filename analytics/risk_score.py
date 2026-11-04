from analytics.aml_labels import get_label
from chains.common import norm

# How many points each kind of exposure adds
POINTS = {"sanctioned": 60, "mixer": 50, "scam": 40}


def calculate_risk(center, txs):
    center = norm(center)
    score = 0
    reasons = []
    found = {}            # category -> set of names
    counterparties = set()

    # Is the searched wallet itself labeled?
    own = get_label(center)
    if own and own["category"] in POINTS:
        score += POINTS[own["category"]]
        reasons.append(f"This wallet itself is a known {own['category']}: {own['name']}")

    # Who did it trade with?
    for t in txs:
        other = t["to"] if t["from"] == center else t["from"]
        if not other:
            continue
        counterparties.add(other)
        label = get_label(other)
        if label:
            found.setdefault(label["category"], set()).add(label["name"])

    for category, names in found.items():
        names_text = ", ".join(sorted(names))
        if category in POINTS:
            score += POINTS[category]
            reasons.append(f"Sent to or received from a {category}: {names_text}")
        else:
            reasons.append(f"Contact with {category}: {names_text} (no penalty)")

    if len(counterparties) > 30:
        score += 10
        reasons.append(f"Talks to many different wallets ({len(counterparties)})")

    score = min(score, 100)
    if not reasons:
        reasons.append("No known risky wallets found in the recent transactions")

    if score < 30:
        level, color = "Low", "#16a34a"
    elif score < 60:
        level, color = "Medium", "#d97706"
    else:
        level, color = "High", "#dc2626"

    return {"score": score, "level": level, "color": color, "reasons": reasons}