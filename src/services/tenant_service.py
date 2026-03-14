"""
Tenant Service
===============
Business logic for tenant (gabinete) management.
CRUD operations against Supabase via REST client.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from src.config.database import get_supabase_client, get_postgres_pool

logger = logging.getLogger(__name__)

# Simple in-memory cache for get_by_slug
_slug_cache: Dict[str, tuple] = {}  # slug -> (timestamp, data)
_SLUG_CACHE_TTL = 300  # 5 minutes


class TenantService:
    """Service for tenant CRUD operations."""

    TABLE = "agentpolitico_tenants"

    async def list_all(self) -> List[Dict[str, Any]]:
        """List all tenants (superadmin)."""
        supabase = get_supabase_client()
        result = supabase.table(self.TABLE).select("*").order("created_at", desc=True).execute()
        return result.data or []

    async def get_by_id(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get a tenant by ID."""
        supabase = get_supabase_client()
        result = supabase.table(self.TABLE).select("*").eq("id", tenant_id).execute()
        if result.data:
            return result.data[0]
        return None

    async def get_by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        """Get a tenant by slug. Cached for 5 minutes."""
        now = time.time()
        if slug in _slug_cache:
            ts, data = _slug_cache[slug]
            if now - ts < _SLUG_CACHE_TTL:
                return data

        supabase = get_supabase_client()
        result = (
            supabase.table(self.TABLE)
            .select("*")
            .eq("slug", slug)
            .eq("active", True)
            .execute()
        )
        if result.data:
            data = result.data[0]
            _slug_cache[slug] = (now, data)
            return data

        _slug_cache.pop(slug, None)
        return None

    async def create(self, data) -> Dict[str, Any]:
        """Create a new tenant."""
        values = data.model_dump(exclude_unset=True)
        supabase = get_supabase_client()
        result = supabase.table(self.TABLE).insert(values).execute()
        return result.data[0]

    async def update(self, tenant_id: str, data) -> Optional[Dict[str, Any]]:
        """Update a tenant."""
        values = data.model_dump(exclude_unset=True)
        if not values:
            return await self.get_by_id(tenant_id)

        values["updated_at"] = datetime.now(timezone.utc).isoformat()

        supabase = get_supabase_client()
        result = (
            supabase.table(self.TABLE)
            .update(values)
            .eq("id", tenant_id)
            .execute()
        )
        if result.data:
            row = result.data[0]
            # Invalidate slug cache
            _slug_cache.pop(row.get("slug", ""), None)
            return row
        return None

    async def delete(self, tenant_id: str) -> bool:
        """Delete a tenant. CASCADE: also clean PostgreSQL dedicated data."""
        supabase = get_supabase_client()

        # Check if tenant exists
        result = supabase.table(self.TABLE).select("id, slug").eq("id", tenant_id).execute()
        if not result.data:
            return False

        row = result.data[0]

        # Invalidate slug cache
        _slug_cache.pop(row.get("slug", ""), None)

        # Delete from Supabase
        supabase.table(self.TABLE).delete().eq("id", tenant_id).execute()

        # Also clean PostgreSQL dedicated data (follow_up_queue)
        try:
            pg_pool = await get_postgres_pool()
            async with pg_pool.acquire() as conn:
                await conn.execute(
                    "DELETE FROM agentpolitico_follow_up_queue WHERE tenant_id = $1",
                    tenant_id,
                )
        except Exception as e:
            logger.warning(f"Failed to clean PostgreSQL data for tenant {tenant_id}: {e}")

        return True
