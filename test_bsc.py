from chains.bsc import get_all_transactions, MEGANODE_API_KEY

print("Key loaded:", bool(MEGANODE_API_KEY))

address = "0x7E1FdF03Eb3aC35BF0256694D7fBe6B6d7b3E0c8"
txs = get_all_transactions(address, limit=5)
print("Transfers found:", len(txs))
for t in txs[:8]:
    print(t["timestamp_utc"], t["token"], t["value"])