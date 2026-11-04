import time
import requests
from datetime import datetime, timezone

try:
    from config import MEGANODE_API_KEY
except ImportError:
    MEGANODE_API_KEY = ""

BASE_URL = "https://bsc-mainnet.nodereal.io/v1"

# BSC stablecoins use 18 decimals (Ethereum's use 6)
TOKENS = {
    "USDT": {"contract": "0x55d398326f99059fF775485246999027B3197955", "decimals": 18},
    "USDC": {"contract": "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d", "decimals": 18},
}
def _rpc(params):
    """Call MegaNode's nr_getAssetTransfers and return the list of transfers."""
    if not MEGANODE_API_KEY:
        raise Exception("MEGANODE_API_KEY is missing. Add it to config.py.")

    url = f"{BASE_URL}/{MEGANODE_API_KEY}"
    payload = {"jsonrpc": "2.0", "method": "nr_getAssetTransfers",
               "params": [params], "id": 1}

    for attempt in range(4):
        r = requests.post(url, json=payload, timeout=60)
        if r.status_code == 429:
            time.sleep(3 * (attempt + 1))
            continue
        if r.status_code != 200:
            raise Exception(f"MegaNode error {r.status_code}: {r.text[:150]}")
        data = r.json()
        if "error" in data:
            message = str(data["error"])
            if "timeout" in message.lower() and attempt < 3:
                time.sleep(2 * (attempt + 1))     # heavy query: wait and retry
                continue
            raise Exception(f"MegaNode error: {data['error']}")
        return data["result"]["transfers"]
    raise Exception("MegaNode rate limit reached. Wait a minute and try again.")


def _utc(seconds):
    when = datetime.fromtimestamp(int(seconds), tz=timezone.utc)
    return when.strftime("%Y-%m-%d %H:%M:%S")


def _records(transfers, token, decimals):
    out = []
    for t in transfers:
        if not t.get("from") or not t.get("to"):
            continue
        raw = int(t["value"], 16) if t.get("value") else 0
        if raw == 0:
            continue
        out.append({
            "hash": t["hash"],
            "from": t["from"].lower(),
            "to": t["to"].lower(),
            "value": raw / 10**decimals,
            "token": token,
            "timestamp_utc": _utc(t["blockTimeStamp"]),
            "block": int(t["blockNum"], 16),
        })
    return out


def _both_directions(address, category, contract, token, decimals, limit):
    """One call for money going out, one for money coming in."""
    records = []
    for direction in ("fromAddress", "toAddress"):
        params = {
            "category": category,
            direction: address,
            "order": "desc",                 # newest first
            "excludeZeroValue": True,
            "maxCount": hex(limit),          # MegaNode wants a hex string
        }
        if contract:
            params["contractAddresses"] = [contract]
        records += _records(_rpc(params), token, decimals)
        time.sleep(0.3)
    return records


def get_all_transactions(address, limit=50):
    """BNB + USDT + USDC, merged, de-duplicated, newest first."""
    all_txs = _both_directions(address, ["external"], None, "BNB", 18, limit)
    for symbol, info in TOKENS.items():
        all_txs += _both_directions(address, ["20"], info["contract"],
                                    symbol, info["decimals"], limit)

    seen = set()
    unique = []
    for t in all_txs:
        key = (t["hash"], t["token"], t["from"], t["to"], t["value"])
        if key not in seen:             # a self-transfer shows up in both calls
            seen.add(key)
            unique.append(t)

    unique.sort(key=lambda t: t["timestamp_utc"], reverse=True)
    return unique