import json

from flask import Blueprint, render_template, request, flash, redirect, abort
from flask_login import login_required, current_user

from cases.db import get_case, list_cases, add_node
from chains.common import norm
from chains.registry import CHAINS, is_valid
from tracing.engine import trace, MAX_HOPS, MAX_BREADTH

tracing_bp = Blueprint("tracing", __name__)


@tracing_bp.route("/trace", methods=["GET", "POST"])
@login_required
def trace_page():
    result, error = None, None
    form = {
        "chain": request.values.get("chain", "ethereum"),
        "source": request.values.get("source", "").strip(),
        "destination": request.values.get("destination", "").strip(),
        "hops": request.values.get("hops", "2"),
        "breadth": request.values.get("breadth", "3"),
    }

    if request.method == "POST":
        chain = form["chain"]
        if chain not in CHAINS:
            error = "Choose a chain."
        elif not is_valid(chain, form["source"]):
            error = f"The start address doesn't look like a valid {CHAINS[chain]['name']} address."
        elif form["destination"] and not is_valid(chain, form["destination"]):
            error = f"The destination doesn't look like a valid {CHAINS[chain]['name']} address."
        elif form["destination"] and norm(form["destination"]) == norm(form["source"]):
            error = "The start and the destination are the same wallet."
        else:
            try:
                hops, breadth = int(form["hops"]), int(form["breadth"])
            except ValueError:
                hops, breadth = 2, 3
            try:
                result = trace(chain, form["source"], form["destination"], hops, breadth)
            except Exception as e:
                error = str(e)

    return render_template(
        "trace.html", username=current_user.username, form=form,
        result=result, error=error, chains=CHAINS,
        cases=list_cases(current_user.id),
        max_hops=MAX_HOPS, max_breadth=MAX_BREADTH)


@tracing_bp.route("/trace/add", methods=["POST"])
@login_required
def trace_add():
    try:
        case_id = int(request.form["case_id"])
    except (KeyError, ValueError):
        abort(400)
    if not get_case(case_id, current_user.id):
        abort(404)

    chain = request.form.get("chain", "")
    try:
        nodes = json.loads(request.form.get("nodes", "[]"))
    except ValueError:
        nodes = []

    added = 0
    if chain in CHAINS and isinstance(nodes, list):
        for n in nodes[:60]:
            if not isinstance(n, dict):
                continue
            address = norm(str(n.get("address", "")))
            if not is_valid(chain, address):
                continue
            kind = "exchange point" if n.get("kind") == "exchange point" else "wallet"
            added += add_node(case_id, address, chain, kind,
                              str(n.get("label", ""))[:80], str(n.get("note", ""))[:200])

    flash(f"Added {added} wallet(s) from the trace to the case.")
    return redirect(f"/cases/{case_id}")