from analytics.aml_labels import get_label
from chains.common import norm

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
PREFIX = 6          # for 0x addresses: "0x" + the first 4 characters
SUFFIX = 4          # the last 4 characters
DUST_SHARE = 0.01   # "tiny" = under 1% of the real payment
HIGH, MEDIUM = "#dc2626", "#d97706"


def short(addr):
    return addr[:8] + "..." + addr[-4:]


def looks_alike(a, b):
    """True if two different addresses start and end with the same characters."""
    return (a != b
            and len(a) > PREFIX + SUFFIX and len(b) > PREFIX + SUFFIX
            and a[:PREFIX] == b[:PREFIX] and a[-SUFFIX:] == b[-SUFFIX:])


def detect_poisoning(center, txs):
    """Look for lookalike addresses planted in a wallet's history."""
    center = norm(center)
    paid = {}      # addresses this wallet really paid -> biggest payment per token
    others = {}    # every other counterparty -> its transfers with this wallet

    for t in txs:
        sender, receiver = t["from"], t["to"]
        if not sender or not receiver:
            continue
        if sender == center:
            other, direction = receiver, "out"
        elif receiver == center:
            other, direction = sender, "in"
        else:
            continue
        if other == center or other == ZERO_ADDRESS:
            continue

        others.setdefault(other, []).append(dict(t, direction=direction))

        if direction == "out" and t["value"] and t["value"] > 0:
            info = paid.setdefault(other, {"max": {}, "first": t["timestamp_utc"]})
            info["max"][t["token"]] = max(info["max"].get(t["token"], 0), t["value"])
            info["first"] = min(info["first"], t["timestamp_utc"])

    findings = []

    # ---- 1. Lookalikes that only ever appear with zero or tiny amounts ----
    for fake, items in others.items():
        if fake in paid or get_label(fake):
            continue
        for real, info in paid.items():
            if not looks_alike(fake, real):
                continue

            zero = all(not i["value"] for i in items)
            tiny = all(
                (not i["value"]) or
                (i["token"] in info["max"]
                 and i["value"] <= DUST_SHARE * info["max"][i["token"]])
                for i in items)
            if not tiny:
                continue

            first_seen = min(i["timestamp_utc"] for i in items)
            after = first_seen >= info["first"]
            n_in = sum(1 for i in items if i["direction"] == "in")
            n_out = len(items) - n_in
            parts = []
            if n_in:
                parts.append(f"{n_in} transfer(s) came from the lookalike")
            if n_out:
                parts.append(f"{n_out} transfer(s) appear to be sent to it")

            detail = (
                f"{' and '.join(parts)}, "
                f"{'all with zero value' if zero else 'all tiny amounts'}. "
                f"It first appeared {first_seen} UTC, "
                f"{'after' if after else 'before'} this wallet's real payment to "
                f"{short(real)} ({info['first']} UTC). Attackers hope the owner "
                "later copies the fake address from the history by mistake.")

            severe = zero and after
            findings.append({
                "severity": "High" if severe else "Medium",
                "color": HIGH if severe else MEDIUM,
                "title": "Zero-value lookalike transfer" if zero else "Tiny lookalike transfer",
                "real": real, "fake": fake,
                "detail": detail,
            })
            break

    # ---- 2. Real money sent to two lookalike addresses ----
    ordered = sorted(paid, key=lambda a: paid[a]["first"])
    for i, first in enumerate(ordered):
        for second in ordered[i + 1:]:
            if looks_alike(first, second):
                findings.append({
                    "severity": "High", "color": HIGH,
                    "title": "Real payments sent to two lookalike addresses",
                    "real": first, "fake": second,
                    "detail": ("This wallet sent real value to both addresses. Their first "
                               "and last characters match, so one may belong to an attacker "
                               "and may have been copied by mistake. Check which one was meant.")})

    findings.sort(key=lambda f: f["severity"] != "High")
    return {"findings": findings, "checked": len(others), "paid": len(paid)}


def mark_graph(graph, result):
    """Draw lookalike wallets as red downward triangles."""
    fakes = {f["fake"] for f in result["findings"]}
    for node in graph["nodes"]:
        if node["id"] in fakes:
            node["shape"] = "triangleDown"
            node["size"] = 24
            node["color"] = {"background": "#fb7185", "border": "#be123c"}
            node["borderWidth"] = 3
            node["label"] = node["label"] + "\n[!] lookalike"
    return graph