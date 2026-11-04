import time
import requests
from datetime import datetime, timezone

BASE_URL = "https://blockstream.info/api"


def _get(path):
    """GET from Blockstream, retrying if we are going too fast."""
    for attempt in range(3):
        r = requests.get(BASE_URL + path, timeout=20)
        if r.status_code == 429:
            time.sleep(2 * (attempt + 1))
            continue
        if r.status_code != 200:
            raise Exception(f"Blockstream error {r.status_code}: {r.text[:100]}")
        return r.json()
    raise Exception("Blockstream rate limit reached. Wait a minute and try again.")


def _utc(timestamp):
    when = datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
    return when.strftime("%Y-%m-%d %H:%M:%S")


def _fetch_raw(address, limit):
    """Confirmed transactions, newest first (25 per page)."""
    raw = _get(f"/address/{address}/txs")
    txs = [t for t in raw if t["status"].get("confirmed")]
    page = txs
    while len(txs) < limit and len(page) >= 25:
        time.sleep(0.5)
        page = _get(f"/address/{address}/txs/chain/{txs[-1]['txid']}")
        txs += page
    return txs[:limit]


def _record(t, sender, receiver, satoshi):
    return {
        "hash": t["txid"],
        "from": sender,
        "to": receiver,
        "value": satoshi / 10**8,          # satoshi -> BTC
        "token": "BTC",
        "timestamp_utc": _utc(t["status"]["block_time"]),
        "block": t["status"].get("block_height", 0),
    }


def get_transactions(address, limit=50):
    """Turn Bitcoin's inputs/outputs into simple from -> to records."""
    records = []
    for t in _fetch_raw(address, limit):
        # Distinct input addresses, in order
        senders = []
        for vin in t["vin"]:
            a = (vin.get("prevout") or {}).get("scriptpubkey_address")
            if a and a not in senders:
                senders.append(a)
        if not senders:
            senders = ["coinbase"]          # newly mined coins

        if address in senders:
            # The wallet is spending: one record per payment out
            for vout in t["vout"]:
                to = vout.get("scriptpubkey_address")
                if not to or to == address:  # skip OP_RETURN and change
                    continue
                records.append(_record(t, address, to, vout["value"]))
        else:
            # The wallet is receiving
            received = sum(v["value"] for v in t["vout"]
                           if v.get("scriptpubkey_address") == address)
            if received > 0:
                records.append(_record(t, senders[0], address, received))
    return records