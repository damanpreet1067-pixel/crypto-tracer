CSS = """
/* ---------- Verify page and alerts ---------- */
.verdict { font-size: 30px; font-weight: 700; color: var(--c); margin: 0 0 6px; }
.alert { margin-top: 12px; padding: 12px 14px; border-radius: 12px;
         background: #fff1f2; border: 1px solid #fecdd3; }
.search input[type=file] { padding: 9px; }
.diffbox { background: #f8fafc; border: 1px solid var(--line); border-radius: 12px;
           padding: 10px; font-family: Consolas, monospace; font-size: 12px; overflow-x: auto; }
.dl { white-space: pre-wrap; word-break: break-all; padding: 2px 8px; border-radius: 4px; }
.dl.add { background: #d1fae5; color: #065f46; }
.dl.del { background: #fee2e2; color: #991b1b; }
.dl.ctx { color: #64748b; }
"""

OLD = '<a href="/cases">My Cases</a></span>'
NEW = '<a href="/cases">My Cases</a><a href="/verify">Verify</a></span>'

# 1. Add the styles
path = "static/style.css"
with open(path, encoding="utf-8") as f:
    css = f.read()
if ".verdict" in css:
    print("OK      style.css already has the new styles")
else:
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n" + CSS)
    print("FIXED   style.css: new styles added")

# 2. Add the Verify link to the top bar of four pages
for name in ["dashboard", "cases", "case", "evidence"]:
    path = f"templates/{name}.html"
    with open(path, encoding="utf-8") as f:
        html = f.read()
    if 'href="/verify"' in html:
        print(f"OK      {path} already has the link")
    elif OLD in html:
        with open(path, "w", encoding="utf-8") as f:
            f.write(html.replace(OLD, NEW))
        print(f"FIXED   {path}: Verify link added")
    else:
        print(f"MANUAL  {path}: top bar looks different, add the link by hand")