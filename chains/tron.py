import time
import hashlib
import requests
from datetime import datetime, timezone

try:
    from config import TRONGRID_API_KEY
except ImportError:
    TRONGRID_API_KEY = ""      # works without a key, with lower limits

BASE_URL = "https://api.trongrid.io"
USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def hex_to_base58(hex_address):
    """Convert a Tron hex address (41...) into the normal T... address."""
    raw = bytes.fromhex(hex_address)
    checksum = hashlib.sha256(hashlib.sha256(raw).digest()).digest()[:4]
    data = raw + checksum
    number = int.from_bytes(data, "big")
    out = ""
    while number > 0:
        number, rem = divmod(number, 58)
        out = ALPHABET[rem] + out
    return out


def _get(path, params):
    """Call TronGrid, retrying if we are going too fast."""
    headers = {"TRON-PRO-API-KEY": TRONGRID_API_KEY} if TRONGRID_API_KEY else {}
    for attempt in range(3):
        r = requests.get(BASE_URL + path, params=params, headers=headers, timeout=20)
        if r.status_code == 429:
            time.sleep(2 * (attempt + 1))
            continue
        if r.status_code != 200:
            raise Exception(f"TronGrid error {r.status_code}: {r.text[:100]}")
        data = r.json()
        if not data.get("success", True):
            raise Exception(f"TronGrid error: {data}")
        return data.get("data", [])
    raise Exception("TronGrid rate limit reached. Wait a minute, or add a free API key.")


def _utc(milliseconds):
    when = datetime.fromtimestamp(int(milliseconds) / 1000, tz=timezone.utc)
    return when.strftime("%Y-%m-%d %H:%M:%S")


def get_transactions(address, limit=50):
    """Normal TRX transfers."""
    rows = _get(f"/v1/accounts/{address}/transactions",
                {"limit": limit, "only_confirmed": "true"})
    records = []
    for t in rows:
        contract = t["raw_data"]["contract"][0]
        if contract["type"] != "TransferContract":
            continue                      # smart-contract calls are covered by USDT below
        ret = t.get("ret")
        if ret and ret[0].get("contractRet") != "SUCCESS":
            continue                      # skip failed transactions
        v = contract["parameter"]["value"]
        records.append({
            "hash": t["txID"],
            "from": hex_to_base58(v["owner_address"]),
            "to": hex_to_base58(v["to_address"]),
            "value": v.get("amount", 0) / 10**6,     # sun -> TRX
            "token": "TRX",
            "timestamp_utc": _utc(t["block_timestamp"]),
            "block": t.get("blockNumber", 0),
        })
    return records


def get_usdt_transfers(address, limit=50):
    """USDT (TRC-20) transfers."""
    rows = _get(f"/v1/accounts/{address}/transactions/trc20",
                {"limit": limit, "contract_address": USDT_CONTRACT,
                 "only_confirmed": "true"})
    records = []
    for t in rows:
        decimals = int(t.get("token_info", {}).get("decimals", 6))
        records.append({
            "hash": t["transaction_id"],
            "from": t["from"],
            "to": t["to"],
            "value": int(t["value"]) / 10**decimals,
            "token": "USDT",
            "timestamp_utc": _utc(t["block_timestamp"]),
            "block": 0,
        })
    return records


def get_all_transactions(address, limit=50):
    """TRX + USDT, merged and sorted newest first."""
    txs = get_transactions(address, limit)
    time.sleep(0.5)                       # stay under the free speed limit
    txs += get_usdt_transfers(address, limit)
    txs.sort(key=lambda t: t["timestamp_utc"], reverse=True)
    return txs