CSS = """
/* ---------- Wallet trace ---------- */
.tracebox { background: #fff; border-radius: 18px; padding: 18px; margin: 20px 0;
            box-shadow: 0 8px 24px rgba(99,102,241,.12); border: 1px solid var(--line); }
.tracebox .row { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 10px; align-items: center; }
.tracebox label { font-size: 13px; color: var(--muted); font-weight: 600; }
.grow { flex: 1; min-width: 260px; }
.stats { display: flex; gap: 12px; flex-wrap: wrap; margin: 14px 0; }
.stat { background: #fff; border: 1px solid var(--line); border-radius: 14px; padding: 12px 18px;
        box-shadow: 0 4px 14px rgba(31,37,68,.06); min-width: 140px; }
.stat b { display: block; font-size: 22px; color: var(--ink); }
.stat span { font-size: 12px; color: var(--muted); }
.hopchain { display: flex; align-items: center; flex-wrap: wrap; gap: 6px; margin: 10px 0;
            padding: 14px; background: #fff; border: 1px solid var(--line); border-radius: 14px; }
.chip { padding: 7px 14px; border-radius: 20px; font-size: 13px; font-weight: 600;
        background: #e0f2fe; color: #075985; }
.chip.src { background: #ffedd5; color: #9a3412; }
.chip.dst { background: #dcfce7; color: #166534; }
.arrowbox { text-align: center; font-size: 12px; color: var(--muted); line-height: 1.3; padding: 0 4px; }
.arrowbox b { display: block; color: #16a34a; font-size: 13px; }
.arrowbox i { font-style: normal; font-size: 20px; color: #a5b4fc; }
.warnbox { background: #fffbeb; border: 1px solid #fde68a; color: #92400e;
           padding: 12px 16px; border-radius: 12px; margin: 12px 0; }
.routes li { margin: 6px 0; }
"""

# 1. Styles
with open("static/style.css", encoding="utf-8") as f:
    css = f.read()
if ".hopchain" in css:
    print("OK      style.css already has the trace styles")
else:
    with open("static/style.css", "a", encoding="utf-8") as f:
        f.write("\n" + CSS)
    print("FIXED   style.css: trace styles added")

# 2. app.py
IMPORT = "from forensics.verify import verify_bp"
REGISTER = "app.register_blueprint(verify_bp)"
with open("app.py", encoding="utf-8") as f:
    text = f.read()
if "tracing_bp" in text:
    print("OK      app.py already has the trace blueprint")
elif IMPORT in text and REGISTER in text:
    text = text.replace(IMPORT, IMPORT + "\nfrom tracing.routes import tracing_bp", 1)
    text = text.replace(REGISTER, REGISTER + "\napp.register_blueprint(tracing_bp)", 1)
    with open("app.py", "w", encoding="utf-8") as f:
        f.write(text)
    print("FIXED   app.py: trace blueprint added")
else:
    print("MANUAL  app.py: add these two lines yourself:")
    print("          from tracing.routes import tracing_bp      (with the other imports)")
    print("          app.register_blueprint(tracing_bp)         (below the other register lines)")

# 3. Top-bar link
OLD = '<a href="/verify">Verify</a></span>'
NEW = '<a href="/verify">Verify</a><a href="/trace">Wallet Trace</a></span>'
for name in ["dashboard", "cases", "case", "evidence", "verify"]:
    path = f"templates/{name}.html"
    with open(path, encoding="utf-8") as f:
        html = f.read()
    if 'href="/trace"' in html:
        print(f"OK      {path} already has the link")
    elif OLD in html:
        with open(path, "w", encoding="utf-8") as f:
            f.write(html.replace(OLD, NEW))
        print(f"FIXED   {path}: Wallet Trace link added")
    else:
        print(f"MANUAL  {path}: add <a href=\"/trace\">Wallet Trace</a> after the Verify link")