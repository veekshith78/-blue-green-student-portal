import os
import time
from datetime import datetime, date

from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user, login_required,
    logout_user, current_user
)
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError
from werkzeug.security import generate_password_hash, check_password_hash

# ---------------------------------------------------------------------------
# App / Config
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# Works out of the box with SQLite. Set DATABASE_URL to point at Postgres/MySQL
# in production (see docker-compose.yml).
db_url = os.environ.get("DATABASE_URL", "sqlite:///students.db")
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Which color this instance is (set via env var in docker-compose). Shown on
# the dashboard so you can SEE the blue/green switch happen live.
app.config["DEPLOYMENT_COLOR"] = os.environ.get("DEPLOYMENT_COLOR", "blue")
app.config["APP_VERSION"] = os.environ.get("APP_VERSION", "1.0.0")

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="student")  # student | admin
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    date = db.Column(db.Date, default=date.today)
    status = db.Column(db.String(10), default="present")  # present | absent

    user = db.relationship("User", backref="attendance_records")


class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    due_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.String(300), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ---------------------------------------------------------------------------
# Health / meta endpoints (used by nginx + Kubernetes health checks)
# ---------------------------------------------------------------------------
@app.route("/health")
def health():
    return jsonify(
        status="healthy",
        color=app.config["DEPLOYMENT_COLOR"],
        version=app.config["APP_VERSION"],
        time=datetime.utcnow().isoformat(),
    )


@app.route("/metrics")
def metrics():
    """Very small Prometheus-compatible metrics endpoint."""
    user_count = User.query.count()
    body = (
        "# HELP app_users_total Total registered users\n"
        "# TYPE app_users_total gauge\n"
        f"app_users_total {user_count}\n"
        "# HELP app_up Whether the app is up\n"
        "# TYPE app_up gauge\n"
        f'app_up{{color="{app.config["DEPLOYMENT_COLOR"]}"}} 1\n'
    )
    return body, 200, {"Content-Type": "text/plain; version=0.0.4"}


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or not password:
            flash("All fields are required.", "error")
            return redirect(url_for("register"))

        if User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "error")
            return redirect(url_for("register"))

        user = User(name=name, email=email, role="student")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash("Account created. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "error")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Core app pages
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    notifications = Notification.query.order_by(Notification.created_at.desc()).limit(5).all()
    assignments = Assignment.query.order_by(Assignment.due_date.asc()).limit(5).all()
    attendance_pct = _attendance_percentage(current_user.id)
    return render_template(
        "dashboard.html",
        notifications=notifications,
        assignments=assignments,
        attendance_pct=attendance_pct,
        color=app.config["DEPLOYMENT_COLOR"],
        version=app.config["APP_VERSION"],
    )


@app.route("/attendance")
@login_required
def attendance():
    records = (
        Attendance.query.filter_by(user_id=current_user.id)
        .order_by(Attendance.date.desc())
        .all()
    )
    return render_template("attendance.html", records=records)


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        current_user.name = request.form.get("name", current_user.name)
        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("profile"))
    return render_template("profile.html")


@app.route("/assignments")
@login_required
def assignments():
    items = Assignment.query.order_by(Assignment.due_date.asc()).all()
    return render_template("assignments.html", assignments=items)


# ---------------------------------------------------------------------------
# Admin panel
# ---------------------------------------------------------------------------
def _admin_required():
    if not current_user.is_authenticated or current_user.role != "admin":
        return False
    return True


@app.route("/admin")
@login_required
def admin_panel():
    if not _admin_required():
        flash("Admins only.", "error")
        return redirect(url_for("dashboard"))
    users = User.query.all()
    return render_template("admin.html", users=users)


@app.route("/admin/attendance/mark", methods=["POST"])
@login_required
def admin_mark_attendance():
    if not _admin_required():
        return jsonify(error="forbidden"), 403

    user_id = request.form.get("user_id")
    status = request.form.get("status", "present")
    record = Attendance(user_id=user_id, status=status, date=date.today())
    db.session.add(record)
    db.session.commit()
    return redirect(url_for("admin_panel"))


@app.route("/admin/notify", methods=["POST"])
@login_required
def admin_notify():
    if not _admin_required():
        return jsonify(error="forbidden"), 403

    message = request.form.get("message", "").strip()
    if message:
        db.session.add(Notification(message=message))
        db.session.commit()
    return redirect(url_for("admin_panel"))


def _attendance_percentage(user_id):
    total = Attendance.query.filter_by(user_id=user_id).count()
    if total == 0:
        return 0
    present = Attendance.query.filter_by(user_id=user_id, status="present").count()
    return round((present / total) * 100, 1)


# ---------------------------------------------------------------------------
# Bootstrap DB + a default admin user on first run
#
# Blue and green start at the same instant and both call this. Only one of
# them will actually win the race to create tables / insert the admin user -
# that's expected and fine. We catch the resulting IntegrityError/
# ProgrammingError from the loser, roll back, and move on instead of
# crashing the whole worker.
# ---------------------------------------------------------------------------
def init_db(retries=10, delay=2):
    for attempt in range(1, retries + 1):
        try:
            with app.app_context():
                db.create_all()
                if not User.query.filter_by(email="admin@example.com").first():
                    admin = User(name="Admin", email="admin@example.com", role="admin")
                    admin.set_password("admin123")
                    db.session.add(admin)
                    db.session.add(Notification(message="Welcome to the Student Portal!"))
                    db.session.commit()
            return  # success
        except OperationalError:
            # DB container not ready yet (e.g. "database does not exist" during
            # first-time initialization) - wait and try again.
            print(f"[init_db] Database not ready yet, retrying ({attempt}/{retries})...")
            time.sleep(delay)
        except (IntegrityError, ProgrammingError):
            # Lost the race to another worker/container creating the same
            # tables or the same admin row at the same time. That's fine -
            # the other one succeeded, so just roll back and continue.
            with app.app_context():
                db.session.rollback()
            print("[init_db] Tables/admin already created by another process - continuing.")
            return

    print("[init_db] Gave up waiting for the database. Check the db container logs.")


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
