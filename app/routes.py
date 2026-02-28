from __future__ import annotations
import os
import secrets
from datetime import datetime
from functools import wraps
from typing import Callable, Any

from flask import (
    Blueprint,
    current_app,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    jsonify,
)

from .models import db, User, UserRole, Event, EventCategory, get_user_by_email, registrations
from .admin_logic import get_analytics_payload
import json
from sqlalchemy import text, inspect


def _ensure_csrf_token() -> str:
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


def _validate_csrf() -> bool:
    form_token = request.form.get("csrf_token", "")
    header_token = request.headers.get("X-CSRFToken", "")
    token = form_token or header_token
    session_token = session.get("_csrf_token", "")
    return bool(token) and secrets.compare_digest(token, session_token)

def _save_event_image(file) -> str:
    filename = file.filename or ""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in {".jpg", ".jpeg", ".png"}:
        ext = ".jpg"
    random_name = secrets.token_hex(8) + ext
    out_dir = os.path.join(current_app.root_path, "static", "event_pics")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, random_name)
    try:
        from PIL import Image
        img = Image.open(file)
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
        max_w = 1600
        max_h = 900
        img.thumbnail((max_w, max_h))
        if ext in (".jpg", ".jpeg"):
            img.save(out_path, format="JPEG", quality=85, optimize=True)
        elif ext == ".png":
            img.save(out_path, format="PNG", optimize=True)
        else:
            img.save(out_path)
    except Exception:
        file.stream.seek(0)
        with open(out_path, "wb") as f:
            f.write(file.read())
    return random_name

def login_required(f: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "warning")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)

    return wrapper


main_bp = Blueprint("main", __name__)
auth_bp = Blueprint("auth", __name__)


@main_bp.app_context_processor
def inject_globals():
    return {"csrf_token": _ensure_csrf_token}


@main_bp.route("/")
def index():
    events = db.session.execute(db.select(Event).order_by(Event.start_time.asc())).scalars().all()
    return render_template("index.html", events=events)

@main_bp.route("/dashboard")
def dashboard():
    events = db.session.execute(db.select(Event).order_by(Event.start_time.asc())).scalars().all()
    return render_template("index.html", events=events)

def current_user() -> User | None:
    uid = session.get("user_id")
    if not uid:
        return None
    return db.session.get(User, uid)

@main_bp.route("/event/new", methods=["GET", "POST"])
@login_required
def create_event():
    u = current_user()
    if not u or not u.is_organizer:
        flash("Only organizers can create events.", "error")
        return redirect(url_for("main.index"))
    if request.method == "POST":
        if not _validate_csrf():
            flash("Invalid request token.", "error")
            return redirect(url_for("main.create_event"))

        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        location = request.form.get("location", "").strip()
        capacity_raw = request.form.get("capacity", "0").strip()
        start_raw = request.form.get("start_time", "").strip()

        try:
            capacity = int(capacity_raw)
        except ValueError:
            capacity = 0

        try:
            start_time = datetime.strptime(start_raw, "%Y-%m-%dT%H:%M")
        except ValueError:
            start_time = None

        if not title or not description or not location or capacity <= 0 or not start_time:
            flash("Please provide valid title, description, location, capacity, and date/time.", "error")
            return render_template("create_event.html")

        if start_time <= datetime.utcnow():
            flash("Event date/time must be in the future.", "error")
            return render_template("create_event.html")

        user = u

        image_file = request.files.get("image_file")
        image_filename = "default.jpg"
        if image_file and getattr(image_file, "filename", ""):
            try:
                image_filename = _save_event_image(image_file)
            except Exception:
                image_filename = "default.jpg"

        event = Event(
            title=title,
            description=description,
            location=location,
            start_time=start_time,
            end_time=start_time,
            capacity=capacity,
            image_file=image_filename,
            organizer_id=user.id,
        )
        db.session.add(event)
        db.session.commit()

        flash("Event created successfully.", "success")
        return redirect(url_for("main.dashboard"))

    return render_template("create_event.html")

@main_bp.route("/event/<int:event_id>")
def event_detail(event_id: int):
    event = db.session.get(Event, event_id)
    if not event:
        flash("Event not found.", "error")
        return redirect(url_for("main.index"))
    uid = session.get("user_id")
    joined = False
    if uid:
        exists = db.session.execute(
            db.select(registrations.c.user_id).where(
                registrations.c.user_id == uid, registrations.c.event_id == event.id
            )
        ).first()
        joined = bool(exists)
    spots_left = max(event.capacity - event.seats_taken(), 0)
    return render_template("event_detail.html", event=event, joined=joined, spots_left=spots_left)

@main_bp.route("/register_event/<int:event_id>", methods=["POST"])
@login_required
def register_event(event_id: int):
    if not _validate_csrf():
        return jsonify({"status": "error", "message": "Invalid request token."}), 400
    user = db.session.get(User, session.get("user_id"))
    event = db.session.get(Event, event_id)
    if not event:
        return jsonify({"status": "error", "message": "Event not found."}), 404
    count = db.session.execute(
        db.select(db.func.count()).select_from(registrations).where(registrations.c.event_id == event.id)
    ).scalar_one()
    if count >= event.capacity:
        return jsonify({"status": "error", "message": "Event is at full capacity."}), 409
    existing = db.session.execute(
        db.select(registrations.c.user_id).where(
            registrations.c.user_id == user.id, registrations.c.event_id == event.id
        )
    ).first()
    if existing:
        return jsonify({"status": "error", "message": "Already registered."}), 409
    event.attendees.append(user)
    db.session.commit()
    new_count = db.session.execute(
        db.select(db.func.count()).select_from(registrations).where(registrations.c.event_id == event.id)
    ).scalar_one()
    spots_left = max(event.capacity - new_count, 0)
    return jsonify({"status": "success", "message": "Registered successfully.", "spots_left": spots_left})

@main_bp.route("/my_events")
@login_required
def my_events():
    user = db.session.get(User, session.get("user_id"))
    events = sorted(user.registered_events, key=lambda e: e.start_time)
    return render_template("my_events.html", events=events)

@main_bp.route("/admin/analytics")
@login_required
def admin_analytics():
    role = session.get("user_role")
    if role != UserRole.ADMIN.value:
        flash("Access denied.", "error")
        return redirect(url_for("main.index"))
    data = get_analytics_payload()
    payload_json = json.dumps(data)
    return render_template("admin/analytics.html", data=data, payload_json=payload_json)

@main_bp.route("/organizer/dashboard")
@login_required
def organizer_dashboard():
    user = current_user()
    if not user or not user.is_organizer:
        flash("Organizer access required.", "error")
        return redirect(url_for("main.index"))
    events = db.session.execute(
        db.select(Event).filter_by(organizer_id=user.id).order_by(Event.start_time.asc())
    ).scalars().all()
    event_ids = [e.id for e in events]
    counts_map: dict[int, int] = {}
    if event_ids:
        rows = db.session.execute(
            db.select(registrations.c.event_id, db.func.count(registrations.c.user_id))
            .where(registrations.c.event_id.in_(event_ids))
            .group_by(registrations.c.event_id)
        ).all()
        counts_map = {eid: cnt for eid, cnt in rows}
    total_attendees = sum(counts_map.get(e.id, 0) for e in events)
    total_capacity = sum(e.capacity for e in events) or 0
    utilization = round((total_attendees / total_capacity * 100.0), 2) if total_capacity else 0.0
    top_event = None
    top_count = 0
    for e in events:
        c = counts_map.get(e.id, 0)
        if c > top_count:
            top_event = e
            top_count = c
    table_rows = []
    for e in events:
        taken = counts_map.get(e.id, 0)
        status = "Upcoming"
        if taken >= e.capacity:
            status = "Sold Out"
        elif e.capacity and taken >= int(0.7 * e.capacity):
            status = "Trending"
        table_rows.append(
            {
                "id": e.id,
                "title": e.title,
                "date": e.start_time,
                "capacity": e.capacity,
                "attendees": taken,
                "status": status,
            }
        )
    chart = {
        "labels": [e.title for e in events],
        "counts": [counts_map.get(e.id, 0) for e in events],
    }
    payload_json = json.dumps(chart)
    return render_template(
        "organizer_dashboard.html",
        kpis={
            "total_attendees": total_attendees,
            "capacity_utilization": utilization,
            "top_event_title": top_event.title if top_event else "N/A",
            "top_event_count": top_count,
        },
        rows=table_rows,
        payload_json=payload_json,
    )
@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        if not _validate_csrf():
            flash("Invalid request token.", "error")
            return redirect(url_for("auth.register"))

        email = request.form.get("email", "").strip().lower()
        full_name = request.form.get("full_name", "").strip()
        password = request.form.get("password", "")
        role_raw = request.form.get("role", "student").strip().lower()
        try:
            role = UserRole(role_raw)
        except ValueError:
            role = UserRole.STUDENT

        if not email or not full_name or not password:
            flash("All fields are required.", "error")
            return render_template("register.html")

        if get_user_by_email(email):
            flash("Email already registered.", "error")
            return render_template("register.html")

        user = User(email=email, full_name=full_name, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash("Account created. Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if not _validate_csrf():
            flash("Invalid request token.", "error")
            return redirect(url_for("auth.login"))

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = get_user_by_email(email)

        if not user or not user.check_password(password):
            flash("Invalid credentials.", "error")
            return render_template("login.html")

        session["user_id"] = user.id
        session["user_role"] = user.role.value if hasattr(user.role, "value") else (str(user.role) or UserRole.STUDENT.value)
        session.permanent = True
        flash("Welcome back.", "success")
        return redirect(url_for("main.index"))

    return render_template("login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.index"))

@main_bp.before_app_request
def sanitize_enums():
    if current_app.config.get("SANITIZED_ENUMS"):
        return
    try:
        from sqlalchemy import update
        role_vals = [r.value for r in UserRole]
        cat_vals = [c.value for c in EventCategory]
        u_stmt = update(User.__table__).where(~User.__table__.c.role.in_(role_vals)).values(role=UserRole.STUDENT.value)
        e_stmt = update(Event.__table__).where(~Event.__table__.c.category.in_(cat_vals)).values(category=EventCategory.GENERAL.value)
        db.session.execute(u_stmt)
        db.session.execute(e_stmt)
        db.session.commit()
    except Exception:
        db.session.rollback()
    finally:
        current_app.config["SANITIZED_ENUMS"] = True

@main_bp.before_app_request
def migrate_image_column():
    if current_app.config.get("MIGRATED_IMAGE_FILE"):
        return
    try:
        insp = inspect(db.engine)
        cols = [c["name"] for c in insp.get_columns("events")]
        if "image_file" not in cols:
            with db.engine.begin() as conn:
                conn.execute(text("ALTER TABLE events ADD COLUMN image_file VARCHAR(255) NOT NULL DEFAULT 'default.jpg'"))
    except Exception:
        pass
    finally:
        current_app.config["MIGRATED_IMAGE_FILE"] = True
@main_bp.before_app_request
def seed_dev_data():
    if current_app.config.get("SEED_DEV_DONE"):
        return
    if os.environ.get("CAMPUS_PULSE_SEED_DEV") != "1":
        current_app.config["SEED_DEV_DONE"] = True
        return
    if db.session.execute(db.select(Event)).first():
        current_app.config["SEED_DEV_DONE"] = True
        return
    organizer = db.session.execute(db.select(User).filter_by(role=UserRole.ORGANIZER)).scalar_one_or_none()
    if not organizer:
        organizer = User(email="organizer@example.com", full_name="Campus Organizer", role=UserRole.ORGANIZER)
        organizer.set_password("ChangeMe123!")
        db.session.add(organizer)
        db.session.commit()
    now = datetime.utcnow()
    sample = Event(
        title="Welcome Week",
        description="Kickoff event for the new semester.",
        category=EventCategory.GENERAL,
        location="Main Hall",
        start_time=now,
        end_time=now,
        capacity=100,
        organizer_id=organizer.id,
    )
    db.session.add(sample)
    db.session.commit()
    current_app.config["SEED_DEV_DONE"] = True
