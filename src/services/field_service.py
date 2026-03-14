"""
Field Service
==============
Business logic for contact field configuration management.
CRUD for tenant contact fields and agent contact fields.
"""

import logging
from typing import Optional, List, Dict, Any

from src.config.database import get_supabase_client

logger = logging.getLogger(__name__)


class FieldService:
    """Service for contact field CRUD operations."""

    CONTACT_FIELDS_TABLE = "agentpolitico_tenant_contact_fields"
    AGENT_FIELDS_TABLE = "agentpolitico_tenant_agent_contact_fields"

    async def list_contact_fields(self, tenant_id: str) -> List[Dict[str, Any]]:
        """List all synced contact fields for a tenant."""
        supabase = get_supabase_client()
        resp = supabase.table(self.CONTACT_FIELDS_TABLE).select("*").eq(
            "tenant_id", tenant_id
        ).execute()
        return [self._normalize(r) for r in resp.data]

    async def list_agent_contact_fields(self, agent_id: str) -> List[Dict[str, Any]]:
        """List contact fields configured for a specific agent with instructions."""
        supabase = get_supabase_client()
        resp = supabase.table(self.AGENT_FIELDS_TABLE).select("*").eq(
            "agent_id", agent_id
        ).order("field_order").execute()
        return [self._normalize(r) for r in resp.data]

    async def configure_agent_field(self, agent_id: str, data) -> Dict[str, Any]:
        """Configure a contact field for an agent."""
        values = data.model_dump(exclude_unset=True)
        contact_field_id = values.pop("contact_field_id")
        # Map API field name to DB column name
        if "instruction" in values:
            values["agent_instruction"] = values.pop("instruction")

        insert_data = {"agent_id": agent_id, "contact_field_id": contact_field_id}
        insert_data.update(values)

        supabase = get_supabase_client()
        resp = supabase.table(self.AGENT_FIELDS_TABLE).insert(insert_data).execute()
        return self._normalize(resp.data[0])

    async def update_agent_field(self, config_id: str, data) -> Optional[Dict[str, Any]]:
        """Update an agent contact field config."""
        supabase = get_supabase_client()
        values = data.model_dump(exclude_unset=True)
        # Map API field name to DB column name
        if "instruction" in values:
            values["agent_instruction"] = values.pop("instruction")

        if not values:
            resp = supabase.table(self.AGENT_FIELDS_TABLE).select("*").eq(
                "id", config_id
            ).limit(1).execute()
            if not resp.data:
                return None
            return self._normalize(resp.data[0])

        resp = supabase.table(self.AGENT_FIELDS_TABLE).update(values).eq(
            "id", config_id
        ).execute()

        if not resp.data:
            return None
        return self._normalize(resp.data[0])

    async def get_active_fields_for_agent(self, agent_id: str) -> List[Dict[str, Any]]:
        """Get only active fields for an agent, ordered by field_order. Used at runtime."""
        supabase = get_supabase_client()
        resp = supabase.table(self.AGENT_FIELDS_TABLE).select("*").eq(
            "agent_id", agent_id
        ).eq(
            "active", True
        ).order("field_order").execute()
        return [self._normalize(r) for r in resp.data]

    @staticmethod
    def _normalize(row: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure UUID fields are strings and map DB names to API names."""
        d = dict(row)
        # Map DB column names to API model names
        if "agent_instruction" in d and "instruction" not in d:
            d["instruction"] = d.pop("agent_instruction")
        for key in ("id", "tenant_id", "agent_id", "contact_field_id"):
            if key in d and d[key] is not None:
                d[key] = str(d[key])
        for key in ("created_at", "updated_at", "synced_at"):
            if key in d and d[key] is not None:
                d[key] = str(d[key])
        return d
