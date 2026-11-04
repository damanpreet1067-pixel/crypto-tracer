from collections import Counter
from datetime import datetime
from chains.common import norm
from analytics.aml_labels import get_label


def _time(text):
    return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")


def analyze_behavior(center, txs):
    """Look for suspicious habits in a wallet's transactions."""
    center = norm(center)

    # Ignore zero-value transactions (contract calls, spam)
    real = [t for t in txs
            if t["value"] and t["value"] > 0 and t["from"] and t["to"]]
    incoming = [t for t in real if t["to"] == center]
    outgoing = [t for t in real if t["from"] == center]

    own = get_label(center)
    is_exchange = bool(own and own["category"] == "exchange")

    findings = []
    points = 0
    signals = 0   # used for the mixer likelihood

    # ---- 1. Rapid pass-through ----
    passes = 0
    for out in outgoing:
        out_time = _time(out["timestamp_utc"])
        for inc in incoming:
            if inc["token"] != out["token"]:
                continue
            gap = (out_time - _time(inc["timestamp_utc"])).total_seconds()
            same_size = 0.9 * inc["value"] <= out["value"] <= inc["value"] * 1.0001
            if 0 <= gap <= 3600 and same_size:
                passes += 1
                break
    if passes >= 3:
        findings.append({
            "name": "Rapid pass-through",
            "detail": f"{passes} transfers left this wallet within 1 hour of "
                      "arriving, with almost the same amount."})
        points += 15
        signals += 1

    # ---- 2. Fan-out / fan-in ----
    if not is_exchange:
        receivers = {t["to"] for t in outgoing}
        senders = {t["from"] for t in incoming}
        if len(receivers) >= 10:
            findings.append({
                "name": "Fan-out",
                "detail": f"Sent funds to {len(receivers)} different wallets."})
            points += 10
            signals += 1
        if len(senders) >= 10:
            findings.append({
                "name": "Fan-in",
                "detail": f"Received funds from {len(senders)} different wallets."})
            points += 5
            signals += 1

    # ---- 3. Equal amounts (mixer-style) ----
    if not is_exchange and real:
        counts = Counter((t["token"], round(t["value"], 6)) for t in real)
        (token, amount), times = counts.most_common(1)[0]
        if times >= 5:
            findings.append({
                "name": "Repeated equal amounts",
                "detail": f"The amount {amount:g} {token} appears {times} times. "
                          "Mixers use fixed amounts."})
            points += 10
            signals += 1

    # ---- 4. Dormant, then active ----
    stamps = sorted(_time(t["timestamp_utc"]) for t in real)
    longest = 0
    for earlier, later in zip(stamps, stamps[1:]):
        longest = max(longest, (later - earlier).days)
    if longest >= 180:
        findings.append({
            "name": "Dormant then active",
            "detail": f"Silent for {longest} days, then active again."})
        points += 5

    # ---- 5. Known mixer contact ----
    mixer_names = set()
    if own and own["category"] == "mixer":
        mixer_names.add(own["name"])
    for t in real:
        other = t["to"] if t["from"] == center else t["from"]
        lab = get_label(other)
        if lab and lab["category"] == "mixer":
            mixer_names.add(lab["name"])
    if mixer_names:
        signals += 2   # a known mixer counts double

    if signals >= 3:
        likelihood, color = "High", "#dc2626"
    elif signals == 2:
        likelihood, color = "Medium", "#d97706"
    else:
        likelihood, color = "Low", "#16a34a"

    return {
        "findings": findings,
        "points": points,
        "mixer_likelihood": likelihood,
        "mixer_color": color,
        "mixer_names": sorted(mixer_names),
        "analyzed": len(real),
    }


def apply_to_risk(risk, behavior):
    """Add the behavior points and reasons to an existing risk result."""
    score = min(100, risk["score"] + behavior["points"])

    reasons = list(risk["reasons"])
    for f in behavior["findings"]:
        reasons.append(f"{f['name']}: {f['detail']}")
    if score > risk["score"]:
        # Remove the "nothing found" line, since something was found
        reasons = [r for r in reasons if not r.startswith("No known risky")]

    if score < 30:
        level, color = "Low", "#4ade80"
    elif score < 60:
        level, color = "Medium", "#fbbf24"
    else:
        level, color = "High", "#ef4444"

    return {"score": score, "level": level, "color": color, "reasons": reasons}