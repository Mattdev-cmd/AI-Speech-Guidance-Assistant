"""
Education Management Blueprint.

Flask routes for class scheduling, attendance monitoring,
user management and the management dashboard.
"""

import logging
import secrets
from datetime import datetime
from functools import wraps

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)

from .database import get_db

logger = logging.getLogger(__name__)

DAYS = [
    "Monday", "Tuesday", "Wednesday", "Thursday",
    "Friday", "Saturday", "Sunday",
]

management_bp = Blueprint(
    "management", __name__, template_folder="../templates"
)


# ── Flask-Login user wrapper ──────────────

class FlaskUser(UserMixin):
    """Wraps a database user dict for Flask-Login."""

    def __init__(self, user_dict):
        self.id = user_dict["id"]
        self.username = user_dict["username"]
        self.full_name = user_dict["full_name"]
        self.role = user_dict["role"]


# ── Helpers ───────────────────────────────

def admin_required(f):
    """Decorator: abort 403 if user is not admin."""

    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "admin":
            abort(403)
        return f(*args, **kwargs)

    return decorated


def _check_csrf():
    token = request.form.get("csrf_token", "")
    if not token or token != session.get("csrf_token"):
        abort(403)


# ── CSRF before-request ──────────────────

@management_bp.before_request
def _csrf_setup():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(16)


# ── Auth routes ───────────────────────────

@management_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("management.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        db = get_db()
        user = db.authenticate_user(username, password)
        if user:
            login_user(FlaskUser(user))
            nxt = request.args.get("next")
            return redirect(nxt or url_for("management.dashboard"))
        flash("Invalid username or password.", "error")

    return render_template("login.html")


@management_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out successfully.", "success")
    return redirect(url_for("management.login"))


# ── Dashboard ─────────────────────────────

@management_bp.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    stats = db.get_dashboard_stats()
    today_name = datetime.now().strftime("%A")
    todays_schedules = db.get_schedules(day_of_week=today_name)
    return render_template(
        "dashboard.html",
        active_page="dashboard",
        stats=stats,
        todays_schedules=todays_schedules,
        today_name=today_name,
    )


# ── Schedules ─────────────────────────────

@management_bp.route("/schedules")
@login_required
def schedules():
    db = get_db()
    day_filter = request.args.get("day")
    return render_template(
        "schedules.html",
        active_page="schedules",
        schedules=db.get_schedules(day_of_week=day_filter),
        subjects=db.get_subjects(),
        teachers=db.get_users(role="teacher"),
        classrooms=db.get_classrooms(),
        days=DAYS,
        day_filter=day_filter,
    )


@management_bp.route("/schedules/add", methods=["POST"])
@login_required
@admin_required
def add_schedule():
    _check_csrf()
    db = get_db()
    ok, conflicts = db.create_schedule(
        subject_id=int(request.form["subject_id"]),
        teacher_id=int(request.form["teacher_id"]),
        classroom_id=int(request.form["classroom_id"]),
        day_of_week=request.form["day_of_week"],
        start_time=request.form["start_time"],
        end_time=request.form["end_time"],
    )
    if ok:
        flash("Schedule created successfully.", "success")
    else:
        for c in conflicts:
            flash(f"Conflict: {c}", "error")
    return redirect(url_for("management.schedules"))


@management_bp.route("/schedules/delete/<int:sid>", methods=["POST"])
@login_required
@admin_required
def delete_schedule(sid):
    _check_csrf()
    get_db().delete_schedule(sid)
    flash("Schedule deleted.", "success")
    return redirect(url_for("management.schedules"))


# ── Subjects ──────────────────────────────

@management_bp.route("/subjects/add", methods=["POST"])
@login_required
@admin_required
def add_subject():
    _check_csrf()
    name = request.form.get("name", "").strip()
    code = request.form.get("code", "").strip()
    if name and code:
        if get_db().create_subject(name, code):
            flash(f"Subject '{name}' added.", "success")
        else:
            flash("Subject code already exists.", "error")
    return redirect(url_for("management.schedules"))


@management_bp.route("/subjects/delete/<int:sid>", methods=["POST"])
@login_required
@admin_required
def delete_subject(sid):
    _check_csrf()
    get_db().delete_subject(sid)
    flash("Subject deleted.", "success")
    return redirect(url_for("management.schedules"))


# ── Classrooms ────────────────────────────

@management_bp.route("/classrooms/add", methods=["POST"])
@login_required
@admin_required
def add_classroom():
    _check_csrf()
    name = request.form.get("name", "").strip()
    cap = request.form.get("capacity", "30")
    if name:
        if get_db().create_classroom(name, int(cap)):
            flash(f"Classroom '{name}' added.", "success")
        else:
            flash("Classroom name already exists.", "error")
    return redirect(url_for("management.schedules"))


@management_bp.route("/classrooms/delete/<int:cid>", methods=["POST"])
@login_required
@admin_required
def delete_classroom(cid):
    _check_csrf()
    get_db().delete_classroom(cid)
    flash("Classroom deleted.", "success")
    return redirect(url_for("management.schedules"))


# ── Attendance ────────────────────────────

@management_bp.route("/attendance")
@login_required
def attendance():
    db = get_db()
    schedule_id = request.args.get("schedule_id", type=int)
    date = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    students = []
    selected_schedule = None
    if schedule_id:
        students = db.get_attendance(schedule_id, date)
        scheds = db.get_schedules()
        selected_schedule = next(
            (s for s in scheds if s["id"] == schedule_id), None
        )
    return render_template(
        "attendance.html",
        active_page="attendance",
        schedules=db.get_schedules(),
        students=students,
        schedule_id=schedule_id,
        date=date,
        selected_schedule=selected_schedule,
    )


@management_bp.route("/attendance/mark", methods=["POST"])
@login_required
def mark_attendance():
    _check_csrf()
    db = get_db()
    schedule_id = int(request.form["schedule_id"])
    date = request.form["date"]

    for key, value in request.form.items():
        if key.startswith("status_"):
            student_id = int(key.split("_", 1)[1])
            if value in ("present", "late", "absent"):
                db.mark_attendance(
                    schedule_id, student_id, date, value, current_user.id
                )

    flash("Attendance saved successfully.", "success")
    return redirect(
        url_for(
            "management.attendance", schedule_id=schedule_id, date=date
        )
    )


# ── Users ─────────────────────────────────

@management_bp.route("/users")
@login_required
@admin_required
def users():
    db = get_db()
    return render_template(
        "users.html",
        active_page="users",
        users=db.get_users(),
        subjects=db.get_subjects(),
    )


@management_bp.route("/users/add", methods=["POST"])
@login_required
@admin_required
def add_user():
    _check_csrf()
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    full_name = request.form.get("full_name", "").strip()
    role = request.form.get("role", "student")
    if username and password and full_name and role in ("admin", "teacher", "student"):
        if get_db().create_user(username, password, full_name, role):
            flash(f"User '{full_name}' created.", "success")
        else:
            flash("Username already exists.", "error")
    else:
        flash("All fields are required.", "error")
    return redirect(url_for("management.users"))


@management_bp.route("/users/delete/<int:uid>", methods=["POST"])
@login_required
@admin_required
def delete_user(uid):
    _check_csrf()
    if uid == current_user.id:
        flash("Cannot delete yourself.", "error")
    else:
        get_db().delete_user(uid)
        flash("User deleted.", "success")
    return redirect(url_for("management.users"))


# ── Enrollments ───────────────────────────

@management_bp.route("/enrollments/update", methods=["POST"])
@login_required
@admin_required
def update_enrollments():
    _check_csrf()
    db = get_db()
    student_id = int(request.form["student_id"])
    subject_ids = [int(x) for x in request.form.getlist("subject_ids")]
    db.set_student_enrollments(student_id, subject_ids)
    flash("Enrollments updated.", "success")
    return redirect(url_for("management.users"))


@management_bp.route("/api/enrollments/<int:student_id>")
@login_required
@admin_required
def get_enrollments_api(student_id):
    """Return enrolled subject IDs as JSON for the enrollment modal."""
    from flask import jsonify

    db = get_db()
    enrolled = db.get_student_enrollments(student_id)
    return jsonify([s["id"] for s in enrolled])


# ── Student Self-Enrollment ───────────────

@management_bp.route("/my-enrollments")
@login_required
def my_enrollments():
    if current_user.role != "student":
        flash("Only students can access this page.", "error")
        return redirect(url_for("management.dashboard"))
    db = get_db()
    return render_template(
        "my_enrollments.html",
        active_page="my_enrollments",
        subjects=db.get_subjects(),
        enrolled=db.get_student_enrollments(current_user.id),
    )


@management_bp.route("/my-enrollments/enroll", methods=["POST"])
@login_required
def self_enroll():
    if current_user.role != "student":
        abort(403)
    _check_csrf()
    db = get_db()
    subject_id = int(request.form["subject_id"])
    if db.enroll_student(current_user.id, subject_id):
        flash("Successfully enrolled!", "success")
    else:
        flash("Already enrolled in this subject.", "error")
    return redirect(url_for("management.my_enrollments"))


@management_bp.route("/my-enrollments/drop", methods=["POST"])
@login_required
def self_drop():
    if current_user.role != "student":
        abort(403)
    _check_csrf()
    db = get_db()
    subject_id = int(request.form["subject_id"])
    db.unenroll_student(current_user.id, subject_id)
    flash("Subject dropped.", "success")
    return redirect(url_for("management.my_enrollments"))
