import importlib
import os

# (file, text that must be present, how many times)
CHECKS = [
    ("app.py", "from analytics.poisoning import detect_poisoning, mark_graph", 1),
    ("app.py", "from forensics.verify import verify_bp", 1),
    ("app.py", "app.register_blueprint(verify_bp)", 1),
    ("app.py", "poisoning = None", 1),
    ("app.py", "poisoning = detect_poisoning(address, txs)", 1),
    ("app.py", "graph = mark_graph(graph, poisoning)", 1),
    ("app.py", "poisoning=poisoning", 1),
    ("templates/dashboard.html", "{% if poisoning %}", 1),
    ("templates/dashboard.html", "<b>Alerts:</b>", 1),
    ("templates/dashboard.html", 'href="/verify"', 1),
    ("templates/cases.html", 'href="/verify"', 1),
    ("templates/case.html", 'href="/verify"', 1),
    ("templates/evidence.html", 'href="/verify"', 1),
    ("templates/verify.html", "Verify an evidence file", 1),
    ("static/style.css", ".verdict", 1),
    ("static/style.css", ".alert", 1),
    ("static/style.css", ".diffbox", 1),
]

print("=== New files exist ===")
for path in ["analytics/poisoning.py", "forensics/verify.py", "templates/verify.html"]:
    print("OK     " if os.path.exists(path) else "MISSING", path)

print("\n=== Edits are in place ===")
for path, text, expected in CHECKS:
    if not os.path.exists(path):
        print("MISSING FILE", path)
        continue
    with open(path, encoding="utf-8") as f:
        found = f.read().count(text)
    status = "OK     " if found == expected else "PROBLEM"
    print(f"{status} {path}: found {found}x (expected {expected}x)  <- {text}")

print("\n=== New modules import cleanly ===")
for module in ["analytics.poisoning", "forensics.verify"]:
    try:
        importlib.import_module(module)
        print("OK     ", module)
    except Exception as e:
        print("BROKEN ", module, "->", e)