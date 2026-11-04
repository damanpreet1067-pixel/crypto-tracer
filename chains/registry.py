import re
from chains.ethereum import get_all_transactions as eth_fetch
from chains.bitcoin import get_transactions as btc_fetch
from chains.tron import get_all_transactions as tron_fetch
from chains.bsc import get_all_transactions as bsc_fetch

CHAINS = {
    "ethereum": {
        "name": "Ethereum",
        "fetch": eth_fetch,
        "pattern": r"0x[a-fA-F0-9]{40}",
        "hint": "start with 0x and be 42 characters long",
    },
    "bsc": {
        "name": "BSC (BNB Chain)",
        "fetch": bsc_fetch,
        "pattern": r"0x[a-fA-F0-9]{40}",
        "hint": "start with 0x and be 42 characters long",
    },
    "bitcoin": {
        "name": "Bitcoin",
        "fetch": btc_fetch,
        "pattern": r"(bc1[a-z0-9]{25,87}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})",
        "hint": "start with 1, 3 or bc1",
    },
    "tron": {
        "name": "Tron",
        "fetch": tron_fetch,
        "pattern": r"T[1-9A-HJ-NP-Za-km-z]{33}",
        "hint": "start with T and be 34 characters long",
    },
}


def is_valid(chain, address):
    info = CHAINS.get(chain)
    return bool(info and re.fullmatch(info["pattern"], address))