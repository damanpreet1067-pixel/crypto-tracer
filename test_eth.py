from chains.ethereum import get_transactions

# A famous public wallet (Vitalik Buterin's), safe to use for testing
address = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"

txs = get_transactions(address, limit=5)

for t in txs:
    print(t["timestamp_utc"], "|", t["from"][:10], "->", t["to"][:10], "|", t["value"], "ETH")