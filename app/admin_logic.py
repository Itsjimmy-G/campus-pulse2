from __future__ import annotations
from datetime import datetime, timedelta
from typing import Dict, Any
from sqlalchemy import func

from .models import db, User, Event, registrations


def _date_list(days: int) -> list[datetime]:
    today = datetime.utcnow().date()
    return [today - timedelta(days=i) for i in reversed(range(days))]


def get_kpis() -> Dict[str, float]:
    total_users = db.session.execute(db.select(func.count(User.id))).scalar_one()
    total_regs = db.session.execute(db.select(func.count()).select_from(registrations)).scalar_one()
    engagement = (total_regs / total_users * 100.0) if total_users else 0.0
    total_capacity = db.session.execute(db.select(func.sum(Event.capacity))).scalar() or 0
    fill = (total_regs / total_capacity * 100.0) if total_capacity else 0.0
    now = datetime.utcnow()
    last7_start = now - timedelta(days=7)
    prev7_start = now - timedelta(days=14)
    last7 = db.session.execute(
        db.select(func.count(User.id)).where(User.created_at >= last7_start)
    ).scalar_one()
    prev7 = db.session.execute(
        db.select(func.count(User.id)).where(User.created_at >= prev7_start, User.created_at < last7_start)
    ).scalar_one()
    growth = ((last7 - prev7) / prev7 * 100.0) if prev7 else (100.0 if last7 > 0 else 0.0)
    return {"engagement_rate": round(engagement, 2), "fill_rate": round(fill, 2), "growth_7d": round(growth, 2)}


def get_registration_trends(days: int = 30) -> Dict[str, list]:
    dlist = _date_list(days)
    q = db.session.execute(
        db.select(func.date(registrations.c.registered_at), func.count())
        .where(registrations.c.registered_at >= dlist[0])
        .group_by(func.date(registrations.c.registered_at))
        .order_by(func.date(registrations.c.registered_at))
    ).all()
    counts_by_day = {str(row[0]): row[1] for row in q}
    labels = [d.isoformat() for d in dlist]
    series = [counts_by_day.get(lbl, 0) for lbl in labels]
    return {"labels": labels, "series": series}


def get_category_popularity() -> Dict[str, list]:
    q = db.session.execute(
        db.select(Event.category, func.count())
        .select_from(Event)
        .join(registrations, registrations.c.event_id == Event.id)
        .group_by(Event.category)
        .order_by(func.count().desc())
    ).all()
    labels = [str(row[0].value if hasattr(row[0], "value") else row[0]) for row in q]
    counts = [row[1] for row in q]
    return {"labels": labels, "counts": counts}


def get_demand_heatmap(limit: int = 5) -> Dict[str, list]:
    sub = (
        db.select(Event.id, Event.title, Event.capacity, func.count(registrations.c.user_id).label("att"))
        .select_from(Event)
        .join(registrations, registrations.c.event_id == Event.id, isouter=True)
        .group_by(Event.id, Event.title, Event.capacity)
        .order_by(func.count(registrations.c.user_id).desc())
        .limit(limit)
        .subquery()
    )
    rows = db.session.execute(db.select(sub.c.title, sub.c.capacity, sub.c.att)).all()
    labels = [r[0] for r in rows]
    capacity = [int(r[1] or 0) for r in rows]
    attendance = [int(r[2] or 0) for r in rows]
    return {"labels": labels, "capacity": capacity, "attendance": attendance}


def get_analytics_payload() -> Dict[str, Any]:
    return {
        "kpis": get_kpis(),
        "trends": get_registration_trends(30),
        "categories": get_category_popularity(),
        "heatmap": get_demand_heatmap(5),
    }
