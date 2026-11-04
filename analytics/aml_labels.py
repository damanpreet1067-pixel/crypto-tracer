import json
import os

LABELS_PATH = os.path.join("data", "labels.json")


def load_labels():
    with open(LABELS_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    return {addr.lower(): info for addr, info in raw.items()}


LABELS = load_labels()


def get_label(address):
    """Return {'name':..., 'category':...} or None if the wallet is unknown."""
    if not address:
        return None
    return LABELS.get(address.lower())