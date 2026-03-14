"""
Helena Sync Service (Multi-Tenant)
===================================
Sincroniza dados do Helena CRM nas tabelas de configuracao
do tenant no Supabase RDG via REST client.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from src.config.database import get_supabase_client
from src.services.helena_client import HelenaClient

logger = logging.getLogger(__name__)

PANELS_TABLE = "agentpolitico_tenant_panels"
STEPS_TABLE = "agentpolitico_tenant_panel_steps"
CUSTOM_FIELDS_TABLE = "agentpolitico_tenant_panel_custom_fields"
CONTACT_FIELDS_TABLE = "agentpolitico_tenant_contact_fields"
DEPARTMENTS_TABLE = "agentpolitico_tenant_departments"
TENANTS_TABLE = "agentpolitico_tenants"


class HelenaSyncService:
    """Sincroniza dados do Helena CRM para tabelas do tenant no Supabase."""

    async def close(self) -> None:
        pass

    async def sync_all(self, tenant_id: str, helena_token: str) -> Dict[str, Any]:
        started_at = datetime.now(timezone.utc)
        errors: List[str] = []

        async with HelenaClient(api_token=helena_token) as client:
            panels_count = 0
            departments_count = 0
            fields_count = 0

            try:
                panels_count = await self.sync_panels(tenant_id, client)
                logger.info("Synced %d panels for tenant %s", panels_count, tenant_id)
            except Exception as exc:
                msg = f"sync_panels failed: {exc}"
                logger.exception(msg)
                errors.append(msg)

            try:
                departments_count = await self.sync_departments(tenant_id, client)
                logger.info("Synced %d departments for tenant %s", departments_count, tenant_id)
            except Exception as exc:
                msg = f"sync_departments failed: {exc}"
                logger.exception(msg)
                errors.append(msg)

            try:
                fields_count = await self.sync_contact_fields(tenant_id, client)
                logger.info("Synced %d contact fields for tenant %s", fields_count, tenant_id)
            except Exception as exc:
                msg = f"sync_contact_fields failed: {exc}"
                logger.exception(msg)
                errors.append(msg)

        finished_at = datetime.now(timezone.utc)

        if not errors:
            status = "success"
        elif panels_count or departments_count or fields_count:
            status = "partial"
        else:
            status = "error"

        return {
            "panels": panels_count,
            "departments": departments_count,
            "contact_fields": fields_count,
            "synced_at": finished_at.isoformat(),
            "duration_seconds": (finished_at - started_at).total_seconds(),
            "status": status,
            "errors": errors,
        }

    async def sync_panels(self, tenant_id: str, client: HelenaClient) -> int:
        panels = await client.get_panels()
        if not panels:
            logger.warning("Helena returned 0 panels for tenant %s", tenant_id)
            return 0

        supabase = get_supabase_client()
        now = datetime.now(timezone.utc).isoformat()
        synced_helena_ids: List[str] = []

        for panel in panels:
            # Skip personal panels (scope USER = "Minhas tarefas")
            if panel.get("scope") == "USER":
                continue

            helena_panel_id = str(panel.get("id") or panel.get("_id") or "")
            if not helena_panel_id:
                continue

            synced_helena_ids.append(helena_panel_id)
            panel_name = panel.get("title") or panel.get("name") or ""

            # Upsert panel
            upsert_data = {
                "tenant_id": tenant_id,
                "helena_panel_id": helena_panel_id,
                "panel_name": panel_name,
                "sync_status": "synced",
                "synced_at": now,
            }
            resp = supabase.table(PANELS_TABLE).upsert(
                upsert_data,
                on_conflict="tenant_id,helena_panel_id"
            ).execute()

            if not resp.data:
                logger.warning("Failed to upsert panel %s", helena_panel_id)
                continue

            tenant_panel_id = str(resp.data[0]["id"])

            # Sync steps
            try:
                steps = await client.get_panel_steps(helena_panel_id)
            except Exception as exc:
                logger.warning("Failed to get steps for panel %s: %s", helena_panel_id, exc)
                steps = []

            for idx, step in enumerate(steps):
                helena_step_id = str(step.get("id") or step.get("_id") or "")
                if not helena_step_id:
                    continue

                step_data = {
                    "tenant_panel_id": tenant_panel_id,
                    "helena_step_id": helena_step_id,
                    "step_name": step.get("title") or step.get("name") or "",
                    "step_order": step.get("position") or step.get("order") or idx,
                    "synced_at": now,
                }
                supabase.table(STEPS_TABLE).upsert(
                    step_data,
                    on_conflict="tenant_panel_id,helena_step_id"
                ).execute()

            # Sync custom fields
            try:
                custom_fields = await client.get_panel_custom_fields(helena_panel_id)
            except Exception as exc:
                logger.warning("Failed to get custom fields for panel %s: %s", helena_panel_id, exc)
                custom_fields = []

            for field in custom_fields:
                helena_field_id = str(field.get("id") or field.get("_id") or field.get("key") or "")
                if not helena_field_id:
                    continue

                field_data = {
                    "tenant_panel_id": tenant_panel_id,
                    "helena_field_id": helena_field_id,
                    "helena_field_name": field.get("name", helena_field_id),
                    "sync_status": "synced",
                    "synced_at": now,
                }
                supabase.table(CUSTOM_FIELDS_TABLE).upsert(
                    field_data,
                    on_conflict="tenant_panel_id,helena_field_id"
                ).execute()

        # Mark orphaned panels
        if synced_helena_ids:
            existing = supabase.table(PANELS_TABLE).select("id,helena_panel_id").eq(
                "tenant_id", tenant_id
            ).execute()
            for row in existing.data:
                if row["helena_panel_id"] not in synced_helena_ids:
                    supabase.table(PANELS_TABLE).update(
                        {"sync_status": "orphaned"}
                    ).eq("id", str(row["id"])).execute()

        return len(synced_helena_ids)

    async def sync_departments(self, tenant_id: str, client: HelenaClient) -> int:
        departments = await client.get_departments()
        if not departments:
            logger.warning("Helena returned 0 departments for tenant %s", tenant_id)
            return 0

        supabase = get_supabase_client()
        now = datetime.now(timezone.utc).isoformat()
        count = 0

        for dept in departments:
            helena_dept_id = str(dept.get("id") or dept.get("_id") or "")
            if not helena_dept_id:
                continue

            dept_data = {
                "tenant_id": tenant_id,
                "helena_department_id": helena_dept_id,
                "department_name": dept.get("name", ""),
                "synced_at": now,
            }
            supabase.table(DEPARTMENTS_TABLE).upsert(
                dept_data,
                on_conflict="tenant_id,helena_department_id"
            ).execute()
            count += 1

        return count

    async def sync_contact_fields(self, tenant_id: str, client: HelenaClient) -> int:
        fields = await client.get_contact_custom_fields()
        if not fields:
            logger.warning("Helena returned 0 contact fields for tenant %s", tenant_id)
            return 0

        supabase = get_supabase_client()
        now = datetime.now(timezone.utc).isoformat()
        synced_keys: List[str] = []

        for field in fields:
            field_key = str(field.get("key") or field.get("name") or "")
            if not field_key:
                continue

            synced_keys.append(field_key)

            field_data = {
                "tenant_id": tenant_id,
                "helena_field_key": field_key,
                "helena_field_name": field.get("name", field_key),
                "sync_status": "synced",
                "synced_at": now,
            }
            supabase.table(CONTACT_FIELDS_TABLE).upsert(
                field_data,
                on_conflict="tenant_id,helena_field_key"
            ).execute()

        # Mark orphaned fields
        if synced_keys:
            existing = supabase.table(CONTACT_FIELDS_TABLE).select(
                "id,helena_field_key"
            ).eq("tenant_id", tenant_id).execute()
            for row in existing.data:
                if row["helena_field_key"] not in synced_keys:
                    supabase.table(CONTACT_FIELDS_TABLE).update(
                        {"sync_status": "orphaned"}
                    ).eq("id", str(row["id"])).execute()

        return len(synced_keys)
