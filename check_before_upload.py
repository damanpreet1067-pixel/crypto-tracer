import os
import subprocess

tracked = subprocess.run(["git", "ls-files"], capture_output=True, text=True).stdout.split("\n")
tracked = [f.strip() for f in tracked if f.strip()]
print(f"{len(tracked)} files are staged for upload.\n")

problems = 0

print("=== Private files that must NOT be uploaded ===")
for f in tracked:
    if (f == "config.py" or f == "data/secret.key" or f.endswith(".db")
            or f.startswith("venv/") or f.startswith("exports/")):
        print("PROBLEM ", f)
        problems += 1
if problems == 0:
    print("OK      none of them are staged")

print("\n=== Key values inside uploaded files ===")
secrets = {}
try:
    import config
    for name in dir(config):
        value = getattr(config, name)
        if name.isupper() and isinstance(value, str) and len(value) >= 8 and "PASTE" not in value:
            secrets[name] = value
except Exception as e:
    print("Could not read config.py:", e)

skip = (".png", ".jpg", ".pdf", ".ico", ".db")
leaks = 0
for f in tracked:
    if f.lower().endswith(skip) or not os.path.isfile(f):
        continue
    with open(f, encoding="utf-8", errors="ignore") as fh:
        text = fh.read()
    for name, value in secrets.items():
        if value in text:
            print(f"PROBLEM  {name} appears inside {f}")
            leaks += 1
if secrets and leaks == 0:
    print(f"OK      none of your {len(secrets)} key(s) appear in any uploaded file")
elif not secrets:
    print("No keys found in config.py to check.")

print("\nSAFE TO UPLOAD" if problems + leaks == 0 else "\nFIX THE PROBLEMS ABOVE FIRST")