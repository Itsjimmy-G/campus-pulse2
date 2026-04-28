from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Dict, Any

from sqlalchemy import func, select, and_, case
from sqlalchemy.orm import Session

from .models import db, User, Event, registrations

class AnalyticsService:
    """
    Encapsulated analytics logic using a Service Pattern.
    Optimized for high performance and minimal DB round-trips.
    """

    @staticmethod
    def get_kpis() -> Dict[str, float]:
        # 1. Use a single query to get multiple counts/sums (Scalar Subqueries or CTEs)
        # We handle Timezones correctly using modern Python datetime standards
        now = datetime.now(timezone.utc)
        last7_start = now - timedelta(days=7)
        prev7_start = now - timedelta(days=14)

        # Senior Move: Get total users, total registrations, and total capacity in ONE hit
        core_stats = db.session.execute(
            select(
                func.count(User.id).label("total_users"),
                select(func.count()).select_from(registrations).scalar_subquery().label("total_regs"),
                select(func.sum(Event.capacity)).scalar_subquery().label("total_capacity")
            )
        ).mappings().one()

        # Growth metrics (Single query using CASE statements)
        growth_stats = db.session.execute(
            select(
                func.count(case((User.created_at >= last7_start, 1))).label("last7"),
                func.count(case((and_(User.created_at >= prev7_start, User.created_at < last7_start), 1))).label("prev7")
            )
        ).mappings().one()

        u, r, c = core_stats["total_users"], core_stats["total_regs"], core_stats["total_capacity"] or 0
        l7, p7 = growth_stats["last7"], growth_stats["prev7"]

        return {
            "engagement_rate": round((r / u * 100.0), 2) if u else 0.0,
            "fill_rate": round((r / c * 100.0), 2) if c else 0.0,
            "growth_7d": round(((l7 - p7) / p7 * 100.0), 2) if p7 else (100.0 if l7 > 0 else 0.0)
        }

    @staticmethod
    def get_registration_trends(days: int = 30) -> Dict[str, list]:
        # Optimize by generating the date range in Python to fill gaps (Zero-padding)
        start_date = (datetime.now(timezone.utc) - timedelta(days=days)).date()
        
        # Aggregate in DB
        trend_query = db.session.execute(
            select(func.date(registrations.c.registered_at), func.count())
            .where(registrations.c.registered_at >= start_date)
            .group_by(func.date(registrations.c.registered_at))
            .order_by(func.date(registrations.c.registered_at))
        ).all()

        counts_map = {str(d): count for d, count in trend_query}
        
        # Build clean series
        labels = [(start_date + timedelta(days=i)).isoformat() for i in range(days + 1)]
        series = [counts_map.get(lbl, 0) for lbl in labels]
        
        return {"labels": labels, "series": series}

    @staticmethod
    def get_category_popularity() -> Dict[str, list]:
        # Using Mappings for cleaner row access
        results = db.session.execute(
            select(Event.category, func.count(registrations.c.user_id).label("count"))
            .join(registrations, registrations.c.event_id == Event.id)
            .group_by(Event.category)
            .order_by(func.count(registrations.c.user_id).desc())
        ).all()

        return {
            "labels": [str(r[0].value) for r in results],
            "counts": [r[1] for r in results]
        }

def get_analytics_payload() -> Dict[str, Any]:
    """Unified entry point for the Admin Dashboard."""
    # We call the service methods
    service = AnalyticsService()
    return {
        "kpis": service.get_kpis(),
        "trends": service.get_registration_trends(30),
        "categories": service.get_category_popularity(),
        "heatmap": get_demand_heatmap(5), # Assuming similar optimization
    }
