import difflib
import hashlib
import os
import re

from flask import Blueprint, render_template, request
from flask_login import login_required, current_user

from cases.db import get_conn
from forensics.export import EXPORT_DIR, init_evidence

verify_bp = Blueprint("verify", __name__)

MAX_BYTES = 25 * 1024 * 1024
TEXT_TYPES = (".csv", ".json")


def clean_name(name):
    """Browsers rename repeat downloads to 'file (1).csv'. Undo that for comparing."""
    name = os.path.basename(name or "")
    return re.sub(r" \(\d+\)(?=\.[^.]+$)", "", name)


def user_files(user_id):
    """Only the evidence of cases that belong to this user."""
    conn = get_conn()
    rows = conn.execute("""
        SELECT e.filename, e.sha256, e.created_utc, c.name AS case_name
        FROM evidence_files e JOIN cases c ON c.id = e.case_id
        WHERE c.user_id = ?
        ORDER BY e.id DESC
    """, (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def make_diff(entry, new_bytes):
    """Show which lines changed, using the saved original in the exports folder."""
    name = os.path.basename(entry["filename"])
    if not name.lower().endswith(TEXT_TYPES):
        return {"available": False,
                "reason": "A line-by-line comparison is only available for CSV and JSON files."}

    path = os.path.join(EXPORT_DIR, name)
    if not os.path.exists(path):
        return {"available": False, "reason": "The original copy is no longer in the exports folder."}

    with open(path, "rb") as f:
        old_bytes = f.read()
    if hashlib.sha256(old_bytes).hexdigest() != entry["sha256"]:
        return {"available": False,
                "reason": "The saved copy in the exports folder no longer matches the log either, "
                          "so it cannot be used for comparison."}

    old = old_bytes.decode("utf-8", errors="replace").splitlines()
    new = new_bytes.decode("utf-8", errors="replace").splitlines()
    lines = list(difflib.unified_diff(old, new, "original", "uploaded", lineterm="", n=0))[2:]
    return {"available": True, "lines": lines[:60], "truncated": len(lines) > 60}


def check(data, filename, user_id):
    digest = hashlib.sha256(data).hexdigest()
    files = user_files(user_id)
    result = {"uploaded_name": filename, "sha256": digest, "size": len(data)}

    # 1. The fingerprint is in the log: the file is untouched
    for f in files:
        if f["sha256"] == digest:
            result.update(status="verified", entry=f)
            return result

    # 2. The name is in the log but the fingerprint differs: it was changed
    name = clean_name(filename)
    for f in files:
        if f["filename"] == name:
            result.update(status="modified", entry=f, diff=make_diff(f, data))
            return result

    # 3. Neither
    result["status"] = "unknown"
    return result


@verify_bp.route("/verify", methods=["GET", "POST"])
@login_required
def verify():
    init_evidence()
    result, error = None, None

    if request.method == "POST":
        upload = request.files.get("file")
        if not upload or not upload.filename:
            error = "Choose a file first."
        else:
            data = upload.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                error = "That file is larger than 25 MB."
            else:
                result = check(data, upload.filename, current_user.id)

    return render_template("verify.html", username=current_user.username,
                           result=result, error=error)