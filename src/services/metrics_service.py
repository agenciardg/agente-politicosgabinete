"""
Metrics Service
================
Records and queries attendance events per tenant.
Uses agentpolitico_metrics table via Supabase REST client.
"""

import logging
import json
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, timezone
from collections import defaultdict

from src.config.database import get_supabase_client

logger = logging.getLogger(__name__)


def _parse_period(period: str) -> datetime:
    """Parse a period string into a cutoff datetime."""
    now = datetime.now(timezone.utc)
    if period == "24h":
        return now - timedelta(hours=24)
    elif period == "7d":
        return now - timedelta(days=7)
    elif period == "30d":
        return now - timedelta(days=30)
    else:
        return now - timedelta(days=7)


class MetricsService:
    """Service for recording and querying metrics."""

    TABLE = "agentpolitico_metrics"

    async def record_event(
        self,
        tenant_id: str,
        agent_type: str,
        phone_number: str,
        session_id: str,
        event_type: str,
        panel_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Insert an attendance event."""
        supabase = get_supabase_client()
        data = {
            "tenant_id": tenant_id,
            "agent_type": agent_type,
            "phone_number": phone_number,
            "session_id": session_id,
            "event_type": event_type,
            "panel_name": panel_name,
            "metadata": metadata or {},
        }
        result = supabase.table(self.TABLE).insert(data).execute()
        if result.data:
            return self._normalize(result.data[0])
        return data

    async def get_summary(self, tenant_id: str, period: str = "7d") -> Dict[str, Any]:
        """Calculate summary metrics for a tenant over a period."""
        cutoff = _parse_period(period)
        cutoff_str = cutoff.isoformat()
        supabase = get_supabase_client()

        # Fetch all rows for the period to compute aggregations client-side
        result = (
            supabase.table(self.TABLE)
            .select("session_id,event_type,panel_name,metadata")
            .eq("tenant_id", tenant_id)
            .gte("event_date", cutoff_str)
            .execute()
        )
        rows = result.data or []

        # Total conversations (unique sessions)
        session_ids = set()
        total_transfers = 0
        response_times: List[float] = []
        categories_breakdown: Dict[str, int] = defaultdict(int)

        for row in rows:
            session_ids.add(row.get("session_id"))
            if row.get("event_type") == "transfer":
                total_transfers += 1
            meta = row.get("metadata")
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except (json.JSONDecodeError, TypeError):
                    meta = {}
            if isinstance(meta, dict) and meta.get("response_time_seconds") is not None:
                try:
                    response_times.append(float(meta["response_time_seconds"]))
                except (ValueError, TypeError):
                    pass
            panel = row.get("panel_name")
            if panel is not None:
                categories_breakdown[panel] += 1

        avg_response_time = (
            sum(response_times) / len(response_times) if response_times else 0.0
        )

        return {
            "total_conversations": len(session_ids),
            "total_transfers": total_transfers,
            "avg_response_time_seconds": round(avg_response_time, 2),
            "categories_breakdown": dict(categories_breakdown),
            "period": period,
        }

    async def get_daily_breakdown(self, tenant_id: str, period: str = "7d") -> List[Dict[str, Any]]:
        """Get daily event counts."""
        cutoff = _parse_period(period)
        cutoff_str = cutoff.isoformat()
        supabase = get_supabase_client()

        result = (
            supabase.table(self.TABLE)
            .select("event_date,event_type")
            .eq("tenant_id", tenant_id)
            .gte("event_date", cutoff_str)
            .order("event_date")
            .execute()
        )
        rows = result.data or []

        # Group by date client-side
        daily: Dict[str, Dict[str, int]] = {}
        for row in rows:
            event_date = row.get("event_date", "")
            date_str = event_date[:10] if event_date else ""
            if date_str not in daily:
                daily[date_str] = {"count": 0, "transfers": 0}
            daily[date_str]["count"] += 1
            if row.get("event_type") == "transfer":
                daily[date_str]["transfers"] += 1

        return [
            {"date": date, "count": vals["count"], "transfers": vals["transfers"]}
            for date, vals in sorted(daily.items())
        ]

    async def get_conversation_list(
        self,
        tenant_id: str,
        period: str = "7d",
        category_filter: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get list of conversations with optional category filter."""
        cutoff = _parse_period(period)
        cutoff_str = cutoff.isoformat()
        supabase = get_supabase_client()

        query = (
            supabase.table(self.TABLE)
            .select("*")
            .eq("tenant_id", tenant_id)
            .gte("event_date", cutoff_str)
        )
        if category_filter:
            query = query.eq("panel_name", category_filter)

        query = query.order("event_date", desc=True).limit(100)
        result = query.execute()
        return [self._normalize(r) for r in (result.data or [])]

    @staticmethod
    def _normalize(row: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a row dict (stringify UUIDs/dates, parse metadata)."""
        d = dict(row)
        for key in ("id", "tenant_id"):
            if key in d and d[key] is not None:
                d[key] = str(d[key])
        for key in ("created_at", "event_date"):
            if key in d and d[key] is not None:
                d[key] = str(d[key])
        if "metadata" in d and d["metadata"] is not None:
            if isinstance(d["metadata"], str):
                try:
                    d["metadata"] = json.loads(d["metadata"])
                except (json.JSONDecodeError, TypeError):
                    pass
        return d
