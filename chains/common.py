def norm(address):
    """Ethereum-style addresses (0x...) are case-insensitive, so lowercase them.
    Bitcoin and Tron addresses are case-SENSITIVE, so leave them untouched."""
    if not address:
        return address
    return address.lower() if address.startswith("0x") else address