from analytics.poisoning import detect_poisoning

me   = "0x" + "a" * 40
real = "0x3c7779" + "1" * 30 + "41ab"     # an address the wallet really paid
fake = "0x3c77e3" + "2" * 30 + "41ab"     # same start and end, planted afterwards

txs = [
    {"hash": "0x1", "from": me, "to": real, "value": 70000.0, "token": "USDC",
     "timestamp_utc": "2026-04-01 01:52:47"},
    {"hash": "0x2", "from": me, "to": fake, "value": 0.0, "token": "USDC",
     "timestamp_utc": "2026-04-01 03:26:23"},
]

result = detect_poisoning(me, txs)
for f in result["findings"]:
    print(f["severity"], "-", f["title"])
    print("  real:", f["real"])
    print("  fake:", f["fake"])
    print(" ", f["detail"])