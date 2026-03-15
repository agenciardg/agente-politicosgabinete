"""
Panel Service
==============
Business logic for panel configuration management.
CRUD for tenant panels, agent panels, and field mappings.
"""

import logging
from typing import Optional, List, Dict, Any

from src.config.database import get_supabase_client

logger = logging.getLogger(__name__)


class PanelService:
    """Service for panel CRUD operations."""

    PANELS_TABLE = "agentpolitico_tenant_panels"
    AGENT_PANELS_TABLE = "agentpolitico_tenant_agent_panels"
    STEPS_TABLE = "agentpolitico_tenant_panel_steps"
    CUSTOM_FIELDS_TABLE = "agentpolitico_tenant_panel_custom_fields"
    FIELD_MAPPINGS_TABLE = "agentpolitico_tenant_agent_panel_field_mappings"

    async def list_panels_by_tenant(self, tenant_id: str) -> List[Dict[str, Any]]:
        """List all panels for a tenant with steps and custom fields."""
        supabase = get_supabase_client()

        panels_resp = supabase.table(self.PANELS_TABLE).select("*").eq(
            "tenant_id", tenant_id
        ).execute()

        result = []
        for p in panels_resp.data:
            panel_id = str(p["id"])
            p = self._normalize(p)

            steps_resp = supabase.table(self.STEPS_TABLE).select("*").eq(
                "tenant_panel_id", panel_id
            ).order("step_order").execute()
            p["steps"] = [self._normalize(s) for s in steps_resp.data]

            fields_resp = supabase.table(self.CUSTOM_FIELDS_TABLE).select("*").eq(
                "tenant_panel_id", panel_id
            ).execute()
            p["custom_fields"] = [self._normalize(f) for f in fields_resp.data]

            result.append(p)
        return result

    async def get_panel(self, panel_id: str) -> Optional[Dict[str, Any]]:
        """Get a single panel with steps and custom fields."""
        supabase = get_supabase_client()

        resp = supabase.table(self.PANELS_TABLE).select("*").eq(
            "id", panel_id
        ).limit(1).execute()

        if not resp.data:
            return None

        p = self._normalize(resp.data[0])

        steps_resp = supabase.table(self.STEPS_TABLE).select("*").eq(
            "tenant_panel_id", panel_id
        ).order("step_order").execute()
        p["steps"] = [self._normalize(s) for s in steps_resp.data]

        fields_resp = supabase.table(self.CUSTOM_FIELDS_TABLE).select("*").eq(
            "tenant_panel_id", panel_id
        ).execute()
        p["custom_fields"] = [self._normalize(f) for f in fields_resp.data]

        return p

    async def list_agent_panels(self, agent_id: str) -> List[Dict[str, Any]]:
        """List panels configured for a specific agent with field mappings."""
        supabase = get_supabase_client()

        ap_resp = supabase.table(self.AGENT_PANELS_TABLE).select("*").eq(
            "agent_id", agent_id
        ).execute()

        result = []
        for ap in ap_resp.data:
            d = self._normalize(ap)
            ap_id = str(d["id"])

            mappings_resp = supabase.table(self.FIELD_MAPPINGS_TABLE).select("*").eq(
                "agent_panel_id", ap_id
            ).execute()
            d["field_mappings"] = [self._normalize(m) for m in mappings_resp.data]

            result.append(d)
        return result

    async def configure_agent_panel(self, agent_id: str, data) -> Dict[str, Any]:
        """Configure a panel for an agent."""
        values = data.model_dump(exclude_unset=True)
        tenant_panel_id = values.pop("tenant_panel_id")
        # Map API names to DB column names
        if "step_id" in values:
            values["helena_step_id"] = values.pop("step_id")
        if "department_id" in values:
            values["helena_department_id"] = values.pop("department_id")

        insert_data = {"agent_id": agent_id, "tenant_panel_id": tenant_panel_id}
        insert_data.update(values)

        supabase = get_supabase_client()
        resp = supabase.table(self.AGENT_PANELS_TABLE).insert(insert_data).execute()
        return self._normalize(resp.data[0])

    async def update_agent_panel(self, agent_panel_id: str, data) -> Optional[Dict[str, Any]]:
        """Update an agent panel config."""
        supabase = get_supabase_client()
        values = data.model_dump(exclude_unset=True)
        # Map API names to DB column names
        if "step_id" in values:
            values["helena_step_id"] = values.pop("step_id")
        if "department_id" in values:
            values["helena_department_id"] = values.pop("department_id")

        if not values:
            resp = supabase.table(self.AGENT_PANELS_TABLE).select("*").eq(
                "id", agent_panel_id
            ).limit(1).execute()
            if not resp.data:
                return None
            return self._normalize(resp.data[0])

        resp = supabase.table(self.AGENT_PANELS_TABLE).update(values).eq(
            "id", agent_panel_id
        ).execute()

        if not resp.data:
            return None
        return self._normalize(resp.data[0])

    async def upsert_field_mapping(
        self, agent_panel_id: str, panel_custom_field_id: str,
        storage_instruction: str, active: bool = True, fill_type: str = "auto"
    ) -> Dict[str, Any]:
        """Upsert a field mapping for an agent panel."""
        supabase = get_supabase_client()

        upsert_data = {
            "agent_panel_id": agent_panel_id,
            "panel_custom_field_id": panel_custom_field_id,
            "storage_instruction": storage_instruction,
            "active": active,
            "fill_type": fill_type,
        }

        resp = supabase.table(self.FIELD_MAPPINGS_TABLE).upsert(
            upsert_data, on_conflict="agent_panel_id,panel_custom_field_id"
        ).execute()
        return self._normalize(resp.data[0])

    async def delete_field_mapping(self, mapping_id: str) -> bool:
        """Delete a field mapping."""
        supabase = get_supabase_client()
        resp = supabase.table(self.FIELD_MAPPINGS_TABLE).delete().eq(
            "id", mapping_id
        ).execute()
        return len(resp.data) > 0

    @staticmethod
    def _normalize(row: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure UUID fields are strings and map DB column names to API names."""
        d = dict(row)
        # Map DB column names to API model names
        if "panel_name" in d:
            d["name"] = d.pop("panel_name")
        if "helena_step_id" in d and "step_id" not in d:
            d["step_id"] = d.pop("helena_step_id")
        if "helena_department_id" in d and "department_id" not in d:
            d["department_id"] = d.pop("helena_department_id")
        for key in ("id", "tenant_id", "agent_id", "tenant_panel_id",
                     "agent_panel_id", "panel_custom_field_id",
                     "helena_panel_id", "helena_step_id", "helena_department_id",
                     "helena_field_id"):
            if key in d and d[key] is not None:
                d[key] = str(d[key])
        for key in ("created_at", "updated_at", "synced_at"):
            if key in d and d[key] is not None:
                d[key] = str(d[key])
        return d
