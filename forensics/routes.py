import os
from flask import Blueprint, render_template, send_file, abort
from flask_login import login_required, current_user

from cases.db import get_case, get_case_nodes
from forensics.export import (export_nodes_csv, export_timeline_csv,
                              export_json, get_timeline, list_evidence,
                              init_evidence)
from forensics.report import export_pdf

bp = Blueprint("forensics", __name__)


@bp.route("/cases/<int:case_id>/evidence")
@login_required
def evidence(case_id):
    init_evidence()
    case = get_case(case_id, current_user.id)
    if not case:
        abort(404)
    nodes = get_case_nodes(case_id)
    return render_template(
        "evidence.html", username=current_user.username, case=case,
        timeline=get_timeline(nodes), files=list_evidence(case_id))


@bp.route("/cases/<int:case_id>/export/<kind>")
@login_required
def export(case_id, kind):
    init_evidence()
    case = get_case(case_id, current_user.id)
    if not case:
        abort(404)
    nodes = get_case_nodes(case_id)

    if kind == "nodes_csv":
        path = export_nodes_csv(case, nodes)
    elif kind == "timeline_csv":
        path = export_timeline_csv(case, nodes)
    elif kind == "json":
        path = export_json(case, nodes)
    elif kind == "pdf":
        path = export_pdf(case, nodes)
    else:
        abort(404)

    return send_file(os.path.abspath(path), as_attachment=True)