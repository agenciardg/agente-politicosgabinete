"""
Agent Service
==============
Business logic for agent configuration management.
CRUD operations for agents, followup prompts, and assessor numbers.
"""

import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from src.config.database import get_supabase_client

logger = logging.getLogger(__name__)


class AgentService:
    """Service for agent CRUD operations."""

    TABLE = "agentpolitico_tenant_agents"
    FOLLOWUP_TABLE = "agentpolitico_tenant_agent_followup_prompts"
    ASSESSOR_TABLE = "agentpolitico_assessor_numbers"

    async def list_by_tenant(self, tenant_id: str) -> List[Dict[str, Any]]:
        """List all agents for a tenant."""
        supabase = get_supabase_client()
        result = supabase.table(self.TABLE).select("*").eq("tenant_id", tenant_id).order("created_at", desc=True).execute()
        return [self._normalize(r) for r in result.data]

    async def get_by_id(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get an agent by ID."""
        supabase = get_supabase_client()
        result = supabase.table(self.TABLE).select("*").eq("id", agent_id).limit(1).execute()
        if result.data:
            return self._normalize(result.data[0])
        return None

    async def create(self, data) -> Dict[str, Any]:
        """Create a new agent. Validates max 2 agents per tenant (1 principal + 1 assessor)."""
        values = data.model_dump(exclude_unset=True)
        tenant_id = values.get("tenant_id")
        agent_type = values.get("agent_type")

        supabase = get_supabase_client()

        # Validate max agents per type
        existing = supabase.table(self.TABLE).select("id", count="exact").eq("tenant_id", tenant_id).eq("agent_type", agent_type).execute()
        if existing.count is not None and existing.count >= 1:
            raise ValueError(f"Tenant already has a {agent_type} agent. Max 1 per type.")

        # Validate max 2 agents total
        total = supabase.table(self.TABLE).select("id", count="exact").eq("tenant_id", tenant_id).execute()
        if total.count is not None and total.count >= 2:
            raise ValueError("Tenant already has 2 agents (max: 1 principal + 1 assessor).")

        result = supabase.table(self.TABLE).insert(values).execute()
        return self._normalize(result.data[0])

    async def update(self, agent_id: str, data) -> Optional[Dict[str, Any]]:
        """Update an agent."""
        values = data.model_dump(exclude_unset=True)
        if not values:
            return await self.get_by_id(agent_id)

        values["updated_at"] = datetime.now(timezone.utc).isoformat()

        supabase = get_supabase_client()
        result = supabase.table(self.TABLE).update(values).eq("id", agent_id).execute()
        if result.data:
            return self._normalize(result.data[0])
        return None

    async def delete(self, agent_id: str) -> bool:
        """Delete an agent."""
        supabase = get_supabase_client()
        result = supabase.table(self.TABLE).delete().eq("id", agent_id).execute()
        return len(result.data) > 0

    # ---- Followup Prompts ----

    async def get_followup_prompts(self, agent_id: str) -> List[Dict[str, Any]]:
        """Get all 3 followup prompts for an agent."""
        supabase = get_supabase_client()
        result = supabase.table(self.FOLLOWUP_TABLE).select("*").eq("agent_id", agent_id).order("followup_number").execute()
        return [self._normalize(r) for r in result.data]

    async def upsert_followup_prompt(
        self, agent_id: str, followup_number: int, prompt_template: str, active: bool = True
    ) -> Dict[str, Any]:
        """Upsert a followup prompt for an agent."""
        supabase = get_supabase_client()
        row_data = {
            "agent_id": agent_id,
            "followup_number": followup_number,
            "prompt_template": prompt_template,
            "active": active,
        }
        result = supabase.table(self.FOLLOWUP_TABLE).upsert(
            row_data, on_conflict="agent_id,followup_number"
        ).execute()
        return self._normalize(result.data[0])

    # ---- Assessor Numbers ----

    async def list_assessor_numbers(self, tenant_id: str) -> List[Dict[str, Any]]:
        """List all assessor numbers for a tenant."""
        supabase = get_supabase_client()
        result = supabase.table(self.ASSESSOR_TABLE).select("*").eq("tenant_id", tenant_id).execute()
        return [self._normalize(r) for r in result.data]

    async def add_assessor_number(
        self, tenant_id: str, agent_id: str, phone_number: str, label: Optional[str] = None
    ) -> Dict[str, Any]:
        """Add an assessor phone number."""
        supabase = get_supabase_client()
        row_data = {
            "tenant_id": tenant_id,
            "agent_id": agent_id,
            "phone_number": phone_number,
            "label": label,
        }
        result = supabase.table(self.ASSESSOR_TABLE).insert(row_data).execute()
        return self._normalize(result.data[0])

    async def delete_assessor_number(self, number_id: str) -> bool:
        """Delete an assessor number."""
        supabase = get_supabase_client()
        result = supabase.table(self.ASSESSOR_TABLE).delete().eq("id", number_id).execute()
        return len(result.data) > 0

    async def is_assessor_number(self, tenant_id: str, phone_number: str) -> bool:
        """Check if a phone number is an assessor number for a tenant."""
        supabase = get_supabase_client()
        result = (
            supabase.table(self.ASSESSOR_TABLE)
            .select("id")
            .eq("tenant_id", tenant_id)
            .eq("phone_number", phone_number)
            .eq("active", True)
            .limit(1)
            .execute()
        )
        return len(result.data) > 0

    @staticmethod
    def _normalize(row: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure UUID and datetime fields are strings (Supabase REST already returns strings, but be safe)."""
        d = dict(row)
        for key in ("id", "tenant_id", "agent_id"):
            if key in d and d[key] is not None:
                d[key] = str(d[key])
        for key in ("created_at", "updated_at"):
            if key in d and d[key] is not None:
                d[key] = str(d[key])
        return d
