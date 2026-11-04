import time
import requests
from datetime import datetime, timezone
from config import ETHERSCAN_API_KEY
from chains.tokens import TOKENS

BASE_URL = "https://api.etherscan.io/v2/api"


def _call(params):
    """Call Etherscan and return the list of results (empty if none)."""
    params["apikey"] = ETHERSCAN_API_KEY
    params["chainid"] = 1  # 1 = Ethereum mainnet
    data = requests.get(BASE_URL, params=params, timeout=20).json()

    if data["status"] != "1":
        if "No transactions" in data.get("message", ""):
            return []
        raise Exception(f"Etherscan error: {data.get('message')} {data.get('result')}")
    return data["result"]


def _utc(timestamp):
    when = datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
    return when.strftime("%Y-%m-%d %H:%M:%S")


def get_transactions(address, limit=50):
    """Normal ETH transactions."""
    rows = _call({
        "module": "account", "action": "txlist", "address": address,
        "startblock": 0, "endblock": 99999999,
        "page": 1, "offset": limit, "sort": "desc",
    })
    return [{
        "hash": t["hash"],
        "from": t["from"].lower(),
        "to": t["to"].lower(),
        "value": int(t["value"]) / 10**18,
        "token": "ETH",
        "timestamp_utc": _utc(t["timeStamp"]),
        "block": int(t["blockNumber"]),
    } for t in rows]


def get_token_transfers(address, symbol, limit=50):
    """Transfers of one token (USDT or USDC) for a wallet."""
    info = TOKENS[symbol]
    rows = _call({
        "module": "account", "action": "tokentx", "address": address,
        "contractaddress": info["contract"],
        "startblock": 0, "endblock": 99999999,
        "page": 1, "offset": limit, "sort": "desc",
    })
    return [{
        "hash": t["hash"],
        "from": t["from"].lower(),
        "to": t["to"].lower(),
        "value": int(t["value"]) / 10**info["decimals"],
        "token": symbol,
        "timestamp_utc": _utc(t["timeStamp"]),
        "block": int(t["blockNumber"]),
    } for t in rows]


def get_all_transactions(address, limit=50):
    """ETH + USDT + USDC, merged and sorted newest first."""
    all_txs = get_transactions(address, limit)
    for symbol in TOKENS:
        time.sleep(0.4)  # stay under the free API speed limit
        all_txs += get_token_transfers(address, symbol, limit)

    all_txs.sort(key=lambda t: t["timestamp_utc"], reverse=True)
    return all_txs