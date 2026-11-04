import os
import re
import sqlite3
import bcrypt
from analytics.poisoning import detect_poisoning, mark_graph
from forensics.verify import verify_bp
from tracing.routes import tracing_bp
from forensics.routes import bp as forensics_bp
from analytics.clustering import find_clusters, color_graph
from forensics.export import init_evidence
from analytics.behavior import analyze_behavior, apply_to_risk
from flask import (Flask, render_template, request, redirect, url_for,
                   flash, abort)
from flask_login import (LoginManager, UserMixin, login_user,
                         logout_user, login_required, current_user)
from chains.registry import CHAINS, is_valid
from chains.common import norm
from cache.db import get_transactions_cached
from graph.builder import build_graph
from analytics.risk_score import calculate_risk
from analytics.aml_labels import get_label
from cases.db import (init_cases, create_case, list_cases, get_case,
                      get_case_nodes, add_node, remove_node)

app = Flask(__name__)
app.secret_key = "change-this-to-any-long-random-text"
app.register_blueprint(forensics_bp)
app.register_blueprint(verify_bp)
app.register_blueprint(tracing_bp)
DB_PATH = "data/tracer.db"
os.makedirs("data", exist_ok=True)

ADDRESS_PATTERN = r"0x[a-fA-F0-9]{40}"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


# ---------- Login system setup ----------
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username


@login_manager.user_loader
def load_user(user_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if row:
        return User(row["id"], row["username"])
    return None


# ---------- Login / Register pages ----------
@app.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        if len(username) < 3 or len(password) < 6:
            flash("Username needs 3+ characters and password 6+ characters.")
            return render_template("register.html")

        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

        try:
            conn = get_db()
            conn.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)",
                         (username, hashed))
            conn.commit()
            conn.close()
        except sqlite3.IntegrityError:
            flash("That username is already taken.")
            return render_template("register.html")

        flash("Account created! Please log in.")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        conn = get_db()
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()

        if row and bcrypt.checkpw(password.encode(), row["password_hash"].encode()):
            login_user(User(row["id"], row["username"]))
            return redirect(url_for("dashboard"))

        flash("Wrong username or password.")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# ---------- Dashboard ----------
@app.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    txs = []
    source = None
    error = None
    graph = None
    risk = None
    behavior = None
    clusters = None
    poisoning = None

    # A search can come from the form (POST) or from a link (GET)
    if request.method == "POST":
        address = request.form["address"].strip()
        chain = request.form["chain"]
    else:
        address = request.args.get("address", "").strip()
        chain = request.args.get("chain", "ethereum")

    if chain not in CHAINS:
        chain = "ethereum"

    if address:
        info = CHAINS[chain]
        if not is_valid(chain, address):
            error = f"That doesn't look like a valid {info['name']} address. It should {info['hint']}."
        else:
            try:
                address = norm(address)
                txs, source = get_transactions_cached(
                    address, chain, info["fetch"], limit=50
                )
                graph = build_graph(address, txs)
                risk = calculate_risk(address, txs)
                behavior = analyze_behavior(address, txs)
                risk = apply_to_risk(risk, behavior)
                clusters = find_clusters(address, txs)
                graph = color_graph(graph, clusters)
                poisoning = detect_poisoning(address, txs)
                graph = mark_graph(graph, poisoning)
            except Exception as e:
                error = str(e)

    return render_template(
        "dashboard.html",
        username=current_user.username,
        txs=txs, source=source, address=address, chain=chain,
        error=error, graph=graph, risk=risk, behavior=behavior,
        clusters=clusters, poisoning=poisoning,chains=CHAINS,
        cases=list_cases(current_user.id),
    )

# ---------- Cases ----------
@app.route("/cases", methods=["GET", "POST"])
@login_required
def cases():
    if request.method == "POST":
        name = request.form["name"].strip()
        if name:
            create_case(current_user.id, name)
            flash(f'Case "{name}" created.')
        return redirect(url_for("cases"))

    return render_template("cases.html", username=current_user.username,
                           cases=list_cases(current_user.id))


@app.route("/cases/<int:case_id>")
@login_required
def case_detail(case_id):
    case = get_case(case_id, current_user.id)
    if not case:
        abort(404)
    return render_template("case.html", username=current_user.username,
                           case=case, nodes=get_case_nodes(case_id))


@app.route("/cases/add", methods=["POST"])
@login_required
def case_add():
    case_id = int(request.form["case_id"])
    case = get_case(case_id, current_user.id)
    if not case:
        abort(404)

    chain = request.form["chain"]
    address = request.form["address"].strip()
    note = request.form.get("note", "").strip()

    if chain not in CHAINS or not is_valid(chain, address):
        flash("Invalid address.")
        return redirect(url_for("case_detail", case_id=case_id))
    address = norm(address)

    # The wallet itself
    own = get_label(address)
    added = add_node(case_id, address, chain, "wallet",
                     own["name"] if own else "", note or "Investigated wallet")

    # Exchange endpoints found in its transactions become case nodes too
    txs, _ = get_transactions_cached(address, chain, CHAINS[chain]["fetch"], limit=50)
    exchange_count = 0
    for t in txs:
        other = t["to"] if t["from"] == address else t["from"]
        label = get_label(other)
        if label and label["category"] == "exchange":
            exchange_count += add_node(
                case_id, other, chain, "exchange point", label["name"],
                "Exchange endpoint found while tracing " + address[:10] + "...")

    flash(f"Added {added} wallet and {exchange_count} exchange point(s) to the case.")
    return redirect(url_for("case_detail", case_id=case_id))


@app.route("/cases/<int:case_id>/remove/<int:node_id>", methods=["POST"])
@login_required
def case_remove(case_id, node_id):
    if not get_case(case_id, current_user.id):
        abort(404)
    remove_node(case_id, node_id)
    return redirect(url_for("case_detail", case_id=case_id))


if __name__ == "__main__":
    init_db()
    init_cases()
    app.run(debug=True)
    
if __name__ == "__main__":
    init_db()
    init_cases()
    init_evidence()
    app.run(debug=True)