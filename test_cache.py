from chains.ethereum import get_transactions
from cache.db import get_transactions_cached

address = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"

txs, source = get_transactions_cached(address, "ethereum", get_transactions, limit=5)

print("Data came from:", source)
for t in txs:
    print(t["timestamp_utc"], "|", t["from"][:10], "->", t["to"][:10], "|", t["value"], "ETH")