from __future__ import annotations
import enum
from datetime import datetime
from typing import Optional

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class UserRole(enum.StrEnum):
    STUDENT = "student"
    ORGANIZER = "organizer"
    ADMIN = "admin"

registrations = db.Table(
    "registrations",
    db.Column("user_id", db.Integer, db.ForeignKey("users.id"), nullable=False),
    db.Column("event_id", db.Integer, db.ForeignKey("events.id"), nullable=False),
    db.Column("registered_at", db.DateTime, default=datetime.utcnow, nullable=False),
    db.UniqueConstraint("user_id", "event_id", name="uq_registration"),
)


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(255), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum(UserRole), default=UserRole.STUDENT, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    organized_events = db.relationship("Event", backref="organizer", lazy="select", foreign_keys="Event.organizer_id")
    registered_events = db.relationship(
        "Event",
        secondary=registrations,
        lazy="select",
        back_populates="attendees",
    )

    def set_password(self, password: str) -> None:
        try:
            import bcrypt

            salt = bcrypt.gensalt(rounds=12)
            self.password_hash = bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")
        except Exception:
            from werkzeug.security import generate_password_hash

            self.password_hash = generate_password_hash(password, method="pbkdf2:sha256", salt_length=16)

    def check_password(self, password: str) -> bool:
        try:
            import bcrypt

            return bcrypt.checkpw(password.encode("utf-8"), self.password_hash.encode("utf-8"))
        except Exception:
            from werkzeug.security import check_password_hash

            return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    @property
    def is_organizer(self) -> bool:
        return self.role in (UserRole.ORGANIZER, UserRole.ADMIN)


class EventCategory(enum.StrEnum):
    GENERAL = "general"
    SPORTS = "sports"
    TECH = "tech"
    ARTS = "arts"
    ACADEMIC = "academic"


class Event(db.Model):
    __tablename__ = "events"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.Enum(EventCategory), default=EventCategory.GENERAL, nullable=False, index=True)
    location = db.Column(db.String(255), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    banner_path = db.Column(db.String(512), nullable=True)
    image_file = db.Column(db.String(255), nullable=False, default="default.jpg")
    organizer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    attendees = db.relationship(
        "User",
        secondary=registrations,
        lazy="select",
        back_populates="registered_events",
    )

    def seats_taken(self) -> int:
        return len(self.attendees)

    def has_capacity(self) -> bool:
        return self.seats_taken() < self.capacity

    def can_register(self, user: User) -> bool:
        return self.has_capacity() and user not in self.attendees


def get_user_by_email(email: str) -> Optional[User]:
    return db.session.execute(db.select(User).filter_by(email=email)).scalar_one_or_none()
