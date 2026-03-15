"""
Tenant Config Loader
=====================
Loads and caches multi-tenant configuration from Supabase REST client.
All queries use the Supabase Python client via get_supabase_client().
"""

import logging
import time
from typing import Optional, Dict, Any, List

from src.config.database import get_supabase_client

logger = logging.getLogger(__name__)

# Simple TTL cache (5 min)
_cache: Dict[str, Dict[str, Any]] = {}
CACHE_TTL = 300


def _str_id(row: dict, keys: List[str]) -> dict:
    """Convert UUID fields to strings in-place and return the dict."""
    for key in keys:
        if key in row and row[key] is not None:
            row[key] = str(row[key])
    return row


class TenantConfigLoader:
    """Loads and caches tenant configuration from Supabase."""

    async def load_tenant_config(self, tenant_slug: str) -> dict:
        """Load full tenant config by slug. Cached for 5 minutes."""
        cache_key = f"tenant:{tenant_slug}"
        now = time.time()
        if cache_key in _cache and now - _cache[cache_key]["ts"] < CACHE_TTL:
            return _cache[cache_key]["data"]

        sb = get_supabase_client()
        result = sb.table("agentpolitico_tenants").select("*").eq(
            "slug", tenant_slug
        ).eq("active", True).limit(1).execute()

        if not result.data:
            raise ValueError(f"Tenant not found or inactive: {tenant_slug}")

        tenant = result.data[0]
        _str_id(tenant, ["id"])

        _cache[cache_key] = {"data": tenant, "ts": now}
        return tenant

    async def load_agent_config(self, tenant_id: str, agent_type: str) -> Optional[dict]:
        """Load agent config (persona_prompt, behavior_prompt, etc.)."""
        sb = get_supabase_client()
        result = sb.table("agentpolitico_tenant_agents").select("*").eq(
            "tenant_id", tenant_id
        ).eq("agent_type", agent_type).eq("active", True).limit(1).execute()

        if not result.data:
            return None

        row = result.data[0]
        _str_id(row, ["id", "tenant_id"])
        return row

    async def load_active_panels(self, agent_id: str) -> list:
        """Load panels configured for this agent, with field mappings."""
        sb = get_supabase_client()

        # Use Supabase nested select to join agent_panels with tenant_panels
        result = sb.table("agentpolitico_tenant_agent_panels").select(
            "*, agentpolitico_tenant_panels(*)"
        ).eq("agent_id", agent_id).eq("active", True).execute()

        panels = []
        for row in result.data:
            panel = dict(row)

            # Flatten joined panel data
            joined_panel = panel.pop("agentpolitico_tenant_panels", None) or {}
            panel["helena_panel_id"] = joined_panel.get("helena_panel_id")
            panel["panel_name"] = joined_panel.get("panel_name")
            panel["pre_transfer_requirements"] = row.get("pre_transfer_requirements")

            _str_id(panel, ["id", "agent_id", "tenant_panel_id"])

            # Load field mappings for this panel with nested join
            mappings_result = sb.table(
                "agentpolitico_tenant_agent_panel_field_mappings"
            ).select(
                "*, agentpolitico_tenant_panel_custom_fields(helena_field_id, helena_field_name)"
            ).eq("agent_panel_id", str(panel["id"])).eq("active", True).execute()

            field_mappings = []
            for m in mappings_result.data:
                mapping = dict(m)
                joined_field = mapping.pop(
                    "agentpolitico_tenant_panel_custom_fields", None
                ) or {}
                mapping["helena_field_id"] = joined_field.get("helena_field_id")
                mapping["helena_field_name"] = joined_field.get("helena_field_name")
                field_mappings.append(mapping)

            panel["field_mappings"] = field_mappings
            panels.append(panel)

        return panels

    async def load_active_contact_fields(self, agent_id: str) -> list:
        """Load contact fields agent should collect, ordered by field_order."""
        sb = get_supabase_client()

        result = sb.table("agentpolitico_tenant_agent_contact_fields").select(
            "*, agentpolitico_tenant_contact_fields(helena_field_key, helena_field_name)"
        ).eq("agent_id", agent_id).eq("active", True).order("field_order").execute()

        rows = []
        for r in result.data:
            row = dict(r)
            joined_cf = row.pop(
                "agentpolitico_tenant_contact_fields", None
            ) or {}
            row["helena_field_key"] = joined_cf.get("helena_field_key")
            row["helena_field_name"] = joined_cf.get("helena_field_name")
            rows.append(row)

        return rows

    async def load_followup_prompts(self, agent_id: str) -> dict:
        """Load follow-up prompt templates for agent."""
        sb = get_supabase_client()

        result = sb.table("agentpolitico_tenant_agent_followup_prompts").select(
            "followup_number, prompt_template"
        ).eq("agent_id", agent_id).eq("active", True).order("followup_number").execute()

        return {r["followup_number"]: r["prompt_template"] for r in result.data}

    async def is_assessor_number(self, tenant_id: str, phone_number: str) -> bool:
        """Check if phone is an assessor number (routes to assessor agent)."""
        sb = get_supabase_client()

        result = sb.table("agentpolitico_assessor_numbers").select("id").eq(
            "tenant_id", tenant_id
        ).eq("phone_number", phone_number).eq("active", True).limit(1).execute()

        return len(result.data) > 0

    async def load_full_agent_config(
        self, tenant_slug: str, phone_number: str
    ) -> Dict[str, Any]:
        """
        Convenience method: loads tenant + determines agent type + loads
        agent config, panels, and contact fields in one call.

        Returns a dict with keys:
            tenant_config, agent_config, agent_type, is_assessor,
            active_panels, active_fields, field_mappings
        """
        tenant_config = await self.load_tenant_config(tenant_slug)
        tenant_id = str(tenant_config["id"])

        is_assessor = await self.is_assessor_number(tenant_id, phone_number)
        agent_type = "assessor" if is_assessor else "principal"

        agent_config = await self.load_agent_config(tenant_id, agent_type)
        if not agent_config:
            # Fallback to principal if assessor not configured
            agent_config = await self.load_agent_config(tenant_id, "principal")
            agent_type = "principal"

        agent_id = str(agent_config["id"]) if agent_config else ""

        active_panels = await self.load_active_panels(agent_id) if agent_id else []
        active_fields = await self.load_active_contact_fields(agent_id) if agent_id else []

        # Build field_mappings dict: panel_name -> list of mappings
        field_mappings: Dict[str, Any] = {}
        for panel in active_panels:
            panel_name = panel.get("panel_name", "")
            field_mappings[panel_name] = panel.get("field_mappings", [])

        return {
            "tenant_config": tenant_config,
            "agent_config": agent_config or {},
            "agent_type": agent_type,
            "is_assessor": is_assessor,
            "active_panels": active_panels,
            "active_fields": active_fields,
            "field_mappings": field_mappings,
        }


def invalidate_tenant_cache(tenant_slug: str) -> None:
    """Invalidate cache for a specific tenant slug."""
    cache_key = f"tenant:{tenant_slug}"
    _cache.pop(cache_key, None)


def invalidate_all_cache() -> None:
    """Invalidate all cached tenant configs."""
    _cache.clear()
