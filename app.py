"""TruthGuard AI - main Flask application (routes, auth, history, reports)."""
import json
import os
import re
import uuid
from datetime import datetime
from functools import wraps

from flask import (Flask, Response, abort, flash, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from ai_modules import (DISCLAIMER, analyze_image, analyze_text, analyze_video)
from ai_modules.common import classify
from database import get_db, init_app_db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "instance", "uploads")

IMAGE_EXTS = {"png", "jpg", "jpeg", "webp"}
VIDEO_EXTS = {"mp4", "webm", "mov", "avi"}
MAX_IMAGE_MB = 5
MAX_VIDEO_MB = 50
MIN_TEXT_CHARS = 30
MAX_TEXT_CHARS = 5000

EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
USERNAME_RE = re.compile(r"[A-Za-z0-9_]{3,20}")

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("TRUTHGUARD_SECRET", "change-this-secret-key"),
    DATABASE=os.path.join(BASE_DIR, "instance", "truthguard.db"),
    # Hard cap on request body size (protects the server from huge uploads)
    MAX_CONTENT_LENGTH=(MAX_VIDEO_MB + 1) * 1024 * 1024,
)
os.makedirs(UPLOAD_DIR, exist_ok=True)
init_app_db(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to use this feature.", "warning")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapper


@app.context_processor
def inject_current_user():
    """Makes `current_user` available in every template."""
    user = None
    if "user_id" in session:
        user = get_db().execute(
            "SELECT id, username, full_name, email FROM users WHERE id = ?",
            (session["user_id"],)).fetchone()
    return {"current_user": user}


def is_safe_next(target):
    """Only allow redirects to paths on this site (prevents open redirects)."""
    return bool(target) and target.startswith("/") and not target.startswith("//")


def validate_upload(file, allowed_exts, max_mb):
    """Return an error message, or None if the upload looks acceptable."""
    if file is None or file.filename == "":
        return "Please choose a file to upload."
    if "." not in file.filename:
        return "The file must have an extension."
    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in allowed_exts:
        return f"Unsupported file type. Allowed: {', '.join(sorted(allowed_exts))}."
    file.stream.seek(0, os.SEEK_END)
    size = file.stream.tell()
    file.stream.seek(0)
    if size == 0:
        return "The uploaded file is empty."
    if size > max_mb * 1024 * 1024:
        return f"File is too large. Maximum size is {max_mb} MB."
    return None


def save_upload_temporarily(file):
    """Store the upload under a random name so user filenames are never used on disk."""
    ext = file.filename.rsplit(".", 1)[-1].lower()
    path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4().hex}.{ext}")
    file.save(path)
    return path


def remove_file(path):
    try:
        os.remove(path)
    except OSError:
        pass


def store_analysis(content_type, title, result):
    db = get_db()
    cur = db.execute(
        """INSERT INTO analyses (user_id, content_type, title, score, prediction,
           confidence, mode, explanation, indicators, recommendations, signals, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (session["user_id"], content_type, title[:120], result["score"],
         result["prediction"], result["confidence"], result["mode"],
         result["explanation"], json.dumps(result["indicators"]),
         json.dumps(result["recommendations"]), json.dumps(result["signals"]),
         datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    db.commit()
    return cur.lastrowid


def load_analysis(analysis_id):
    """Fetch one analysis, only if it belongs to the logged-in user."""
    row = get_db().execute(
        "SELECT * FROM analyses WHERE id = ? AND user_id = ?",
        (analysis_id, session["user_id"])).fetchone()
    if row is None:
        abort(404)
    data = dict(row)
    data["indicators"] = json.loads(data["indicators"])
    data["recommendations"] = json.loads(data["recommendations"])
    data["signals"] = json.loads(data["signals"])
    data["color"] = classify(data["score"])[1]
    return data


def build_report(r):
    """Plain-text report that users can download."""
    lines = [
        "TRUTHGUARD AI - ANALYSIS REPORT",
        "=" * 44,
        f"Report ID       : {r['id']}",
        f"Content type    : {r['content_type'].title()}",
        f"Input           : {r['title']}",
        f"Analysed on     : {r['created_at']}",
        f"Analysis mode   : {r['mode']}",
        "",
        f"Authenticity score : {r['score']} / 100",
        f"Prediction         : {r['prediction']}",
        f"Confidence         : {r['confidence']}",
        "",
        "EXPLANATION",
        "-" * 44,
        r["explanation"],
        "",
        "SUSPICIOUS INDICATORS",
        "-" * 44,
    ]
    lines += [f"- {item}" for item in r["indicators"]]
    lines += ["", "CHECK DETAILS", "-" * 44]
    lines += [f"- {s['name']}: {s['detail']} (risk {round(s['risk'] * 100)}%)"
              for s in r["signals"]]
    lines += ["", "VERIFICATION RECOMMENDATIONS", "-" * 44]
    lines += [f"- {item}" for item in r["recommendations"]]
    lines += ["", DISCLAIMER, "",
              "TruthGuard AI - Real Information. A Safer Digital World.",
              "Created by: Ritesh | Guided by: Aaradhna Deshmukh Ma'am"]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public pages
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    total = get_db().execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
    return render_template("index.html", total_analyses=total)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/awareness")
def awareness():
    return render_template("awareness.html")


# ---------------------------------------------------------------------------
# User module: register, login, logout, dashboard, profile
# ---------------------------------------------------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        errors = []
        if len(full_name) < 2:
            errors.append("Full name must be at least 2 characters.")
        if not USERNAME_RE.fullmatch(username):
            errors.append("Username must be 3-20 characters: letters, numbers or underscore.")
        if not EMAIL_RE.fullmatch(email):
            errors.append("Please enter a valid email address.")
        if len(password) < 8:
            errors.append("Password must be at least 8 characters.")
        if password != confirm:
            errors.append("Passwords do not match.")

        db = get_db()
        if not errors:
            taken = db.execute("SELECT 1 FROM users WHERE username = ? OR email = ?",
                               (username, email)).fetchone()
            if taken:
                errors.append("That username or email is already registered.")

        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template("auth.html", mode="register", form=request.form), 400

        db.execute(
            "INSERT INTO users (username, full_name, email, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
            (username, full_name, email, generate_password_hash(password),
             datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        db.commit()
        flash("Account created successfully. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("auth.html", mode="register", form={})


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")
        user = get_db().execute(
            "SELECT * FROM users WHERE username = ? OR email = ?",
            (identifier, identifier.lower())).fetchone()

        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Invalid username/email or password.", "danger")
            return render_template("auth.html", mode="login", form=request.form), 401

        session.clear()
        session["user_id"] = user["id"]
        flash(f"Welcome back, {user['full_name']}!", "success")
        next_url = request.args.get("next")
        return redirect(next_url if is_safe_next(next_url) else url_for("dashboard"))

    return render_template("auth.html", mode="login", form={})


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    uid = session["user_id"]
    totals = db.execute(
        "SELECT COUNT(*) AS total, COALESCE(ROUND(AVG(score)), 0) AS avg_score "
        "FROM analyses WHERE user_id = ?", (uid,)).fetchone()
    by_type = db.execute(
        "SELECT content_type, COUNT(*) AS n FROM analyses WHERE user_id = ? GROUP BY content_type",
        (uid,)).fetchall()
    recent = db.execute(
        "SELECT id, content_type, title, score, prediction, created_at FROM analyses "
        "WHERE user_id = ? ORDER BY id DESC LIMIT 5", (uid,)).fetchall()
    user = db.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    type_counts = {row["content_type"]: row["n"] for row in by_type}
    return render_template("dashboard.html", totals=totals, type_counts=type_counts,
                           recent=recent, user=user)


@app.route("/profile", methods=["POST"])
@login_required
def update_profile():
    db = get_db()
    uid = session["user_id"]
    user = db.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    full_name = request.form.get("full_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    current_pw = request.form.get("current_password", "")
    new_pw = request.form.get("new_password", "")

    if len(full_name) < 2:
        flash("Full name must be at least 2 characters.", "danger")
        return redirect(url_for("dashboard"))
    if not EMAIL_RE.fullmatch(email):
        flash("Please enter a valid email address.", "danger")
        return redirect(url_for("dashboard"))
    clash = db.execute("SELECT 1 FROM users WHERE email = ? AND id != ?", (email, uid)).fetchone()
    if clash:
        flash("That email is already used by another account.", "danger")
        return redirect(url_for("dashboard"))

    new_hash = user["password_hash"]
    if new_pw:
        if not check_password_hash(user["password_hash"], current_pw):
            flash("Your current password is incorrect.", "danger")
            return redirect(url_for("dashboard"))
        if len(new_pw) < 8:
            flash("New password must be at least 8 characters.", "danger")
            return redirect(url_for("dashboard"))
        new_hash = generate_password_hash(new_pw)

    db.execute("UPDATE users SET full_name = ?, email = ?, password_hash = ? WHERE id = ?",
               (full_name, email, new_hash, uid))
    db.commit()
    flash("Profile updated successfully.", "success")
    return redirect(url_for("dashboard"))


# ---------------------------------------------------------------------------
# Detection dashboard and analysis routes
# ---------------------------------------------------------------------------
@app.route("/detect")
@login_required
def detect():
    tab = request.args.get("tab", "text")
    if tab not in {"text", "image", "video"}:
        tab = "text"
    return render_template("detect.html", tab=tab, max_image_mb=MAX_IMAGE_MB,
                           max_video_mb=MAX_VIDEO_MB, min_chars=MIN_TEXT_CHARS,
                           max_chars=MAX_TEXT_CHARS)


@app.route("/analyze/text", methods=["POST"])
@login_required
def analyze_text_route():
    text = request.form.get("news_text", "").strip()
    if len(text) < MIN_TEXT_CHARS or len(text) > MAX_TEXT_CHARS:
        flash(f"Please enter between {MIN_TEXT_CHARS} and {MAX_TEXT_CHARS} characters.", "danger")
        return redirect(url_for("detect", tab="text"))
    result = analyze_text(text)
    analysis_id = store_analysis("text", text[:80], result)
    return redirect(url_for("result", analysis_id=analysis_id))


def _run_upload_analysis(content_type, field, exts, max_mb, analyzer, tab):
    """Shared flow for image and video uploads."""
    file = request.files.get(field)
    error = validate_upload(file, exts, max_mb)
    if error:
        flash(error, "danger")
        return redirect(url_for("detect", tab=tab))

    path = save_upload_temporarily(file)
    try:
        result = analyzer(path)
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("detect", tab=tab))
    finally:
        remove_file(path)  # never keep user uploads after analysis

    analysis_id = store_analysis(content_type, secure_filename(file.filename), result)
    return redirect(url_for("result", analysis_id=analysis_id))


@app.route("/analyze/image", methods=["POST"])
@login_required
def analyze_image_route():
    return _run_upload_analysis("image", "image", IMAGE_EXTS, MAX_IMAGE_MB,
                                analyze_image, "image")


@app.route("/analyze/video", methods=["POST"])
@login_required
def analyze_video_route():
    return _run_upload_analysis("video", "video", VIDEO_EXTS, MAX_VIDEO_MB,
                                analyze_video, "video")


@app.errorhandler(413)
def file_too_large(_error):
    flash(f"The upload is too large. Maximum allowed size is {MAX_VIDEO_MB} MB.", "danger")
    return redirect(url_for("detect"))


@app.route("/result/<int:analysis_id>")
@login_required
def result(analysis_id):
    return render_template("result.html", r=load_analysis(analysis_id))


# ---------------------------------------------------------------------------
# History and reports
# ---------------------------------------------------------------------------
@app.route("/history")
@login_required
def history():
    rows = get_db().execute(
        "SELECT id, content_type, title, score, prediction, mode, created_at "
        "FROM analyses WHERE user_id = ? ORDER BY id DESC",
        (session["user_id"],)).fetchall()
    return render_template("history.html", rows=rows)


@app.route("/history/<int:analysis_id>/delete", methods=["POST"])
@login_required
def delete_analysis(analysis_id):
    db = get_db()
    cur = db.execute("DELETE FROM analyses WHERE id = ? AND user_id = ?",
                     (analysis_id, session["user_id"]))
    db.commit()
    if cur.rowcount:
        flash("Analysis deleted.", "success")
    else:
        flash("Analysis not found.", "danger")
    return redirect(url_for("history"))


@app.route("/report/<int:analysis_id>")
@login_required
def download_report(analysis_id):
    r = load_analysis(analysis_id)
    filename = f"truthguard_report_{analysis_id}.txt"
    return Response(build_report(r), mimetype="text/plain",
                    headers={"Content-Disposition": f"attachment; filename={filename}"})


if __name__ == "__main__":
    app.run(debug=True)
