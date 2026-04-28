from __future__ import annotations
import enum
from datetime import datetime, timezone
from typing import Optional, List

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, String, DateTime, Integer, Text, Enum, select, func
from werkzeug.security import generate_password_hash, check_password_hash

# Senior Tip: Explicitly define a Base for better type checking
class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

class UserRole(enum.StrEnum):
    STUDENT = "student"
    ORGANIZER = "organizer"
    ADMIN = "admin"

class EventCategory(enum.StrEnum):
    GENERAL = "general"
    SPORTS = "sports"
    TECH = "tech"
    ARTS = "arts"
    ACADEMIC = "academic"

# Many-to-Many Association Table
registrations = db.Table(
    "registrations",
    db.Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    db.Column("event_id", Integer, ForeignKey("events.id", ondelete="CASCADE"), primary_key=True),
    db.Column("registered_at", DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)),
)

class User(db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.STUDENT, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    organized_events: Mapped[List["Event"]] = relationship("Event", back_populates="organizer", foreign_keys="[Event.organizer_id]")
    registered_events: Mapped[List["Event"]] = relationship("Event", secondary=registrations, back_populates="attendees")

    def set_password(self, password: str) -> None:
        """Seniors use a single, reliable hashing method for consistency."""
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    @property
    def is_privileged(self) -> bool:
        """Abbreviated logic for permission checking."""
        return self.role in {UserRole.ORGANIZER, UserRole.ADMIN}


class Event(db.Model):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[EventCategory] = mapped_column(Enum(EventCategory), default=EventCategory.GENERAL, index=True)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    image_file: Mapped[str] = mapped_column(String(255), default="default.jpg")
    organizer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    organizer: Mapped["User"] = relationship("User", back_populates="organized_events", foreign_keys=[organizer_id])
    attendees: Mapped[List["User"]] = relationship("User", secondary=registrations, back_populates="registered_events")

    def get_attendee_count(self) -> int:
        """
        Senior Performance Fix: 
        Don't use len(self.attendees). It loads every user object into RAM.
        Query the count directly from the database instead.
        """
        return db.session.query(func.count(registrations.c.user_id)).filter(registrations.c.event_id == self.id).scalar()

    def has_capacity(self) -> bool:
        return self.get_attendee_count() < self.capacity

    def can_register(self, user: User) -> bool:
        if not self.has_capacity():
            return False
        # Check existence without loading the whole list
        exists = db.session.query(registrations).filter_by(user_id=user.id, event_id=self.id).first()
        return exists is None

# Repository Pattern Helper
class UserRepository:
    @staticmethod
    def get_by_email(email: str) -> Optional[User]:
        return db.session.execute(select(User).filter_by(email=email)).scalar_one_or_none()
