"""
Follow-up Service
==================
Manages follow-up scheduling and processing.

Queue table (agentpolitico_follow_up_queue) lives in PostgreSQL dedicated.
Prompt templates & tenant config live in Supabase RDG.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from zoneinfo import ZoneInfo

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from src.config.database import get_supabase_client, get_postgres_pool
from src.config.settings import settings
from src.services.helena_client import HelenaClient
from src.services.memory_service import MemoryService
from src.services.error_service import ErrorService

logger = logging.getLogger(__name__)

SP_TZ = ZoneInfo("America/Sao_Paulo")

QUEUE_TABLE = "agentpolitico_follow_up_queue"
PROMPTS_TABLE = "agentpolitico_tenant_agent_followup_prompts"
TENANTS_TABLE = "agentpolitico_tenants"
EVENTS_TABLE = "agentpolitico_tenant_events"


class FollowupService:
    """Manages follow-up scheduling and processing."""

    def __init__(self) -> None:
        self.memory_service = MemoryService()
        self.error_service = ErrorService()

    # ------------------------------------------------------------------
    # Scheduling
    # ------------------------------------------------------------------

    async def schedule_followup(
        self,
        tenant_id: str,
        session_id: str,
        phone_number: str,
        agent_type: str,
    ) -> None:
        """Schedule first follow-up (configurable minutes from now).

        Called after the agent responds and the citizen has not yet replied.
        Cancels any existing pending follow-ups for this phone/tenant first.
        """
        await self.cancel_pending_followups(tenant_id, phone_number)

        # Get tenant config for timing
        tenant = await self._get_tenant_config(tenant_id)
        delay_minutes = (tenant or {}).get("followup_1_minutes", 20)

        scheduled_at = datetime.now(SP_TZ) + timedelta(minutes=delay_minutes)

        pool = await get_postgres_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                f"""
                INSERT INTO {QUEUE_TABLE}
                    (tenant_id, session_id, phone_number, agent_type,
                     follow_up_number, scheduled_at, status)
                VALUES ($1, $2, $3, $4, $5, $6, 'pending')
                """,
                tenant_id,
                session_id,
                phone_number,
                agent_type,
                1,
                scheduled_at,
            )

        logger.info(
            "Scheduled follow-up 1 for tenant=%s phone=%s at %s",
            tenant_id,
            phone_number,
            scheduled_at.isoformat(),
        )

    async def cancel_pending_followups(
        self,
        tenant_id: str,
        phone_number: str,
    ) -> None:
        """Cancel all pending follow-ups for a phone/tenant.

        Called when the citizen responds.
        """
        pool = await get_postgres_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                f"""
                UPDATE {QUEUE_TABLE}
                SET status = 'cancelled'
                WHERE tenant_id = $1
                  AND phone_number = $2
                  AND status = 'pending'
                """,
                tenant_id,
                phone_number,
            )
        logger.debug(
            "Cancelled pending follow-ups for tenant=%s phone=%s",
            tenant_id,
            phone_number,
        )

    # ------------------------------------------------------------------
    # Processing (called by cron every 1 minute)
    # ------------------------------------------------------------------

    async def process_pending_followups(self) -> Dict[str, Any]:
        """Process all due follow-ups across all tenants.

        Returns:
            Dict with processed, sent, and error counts.
        """
        pool = await get_postgres_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT id, tenant_id, session_id, phone_number, agent_type,
                       follow_up_number
                FROM {QUEUE_TABLE}
                WHERE status = 'pending'
                  AND scheduled_at <= NOW()
                ORDER BY scheduled_at ASC
                """
            )

        processed = 0
        sent = 0
        errors = 0

        for row in rows:
            processed += 1
            try:
                await self._process_single_followup(dict(row))
                sent += 1
            except Exception as e:
                errors += 1
                logger.error(
                    "Failed to process follow-up %s: %s", row["id"], e, exc_info=True
                )
                await self.error_service.log_error(
                    tenant_id=str(row["tenant_id"]),
                    error_type="followup_send_failed",
                    error_message=str(e),
                    context={
                        "followup_id": str(row["id"]),
                        "session_id": row["session_id"],
                        "follow_up_number": row["follow_up_number"],
                    },
                )

        logger.info(
            "Follow-up processing complete: processed=%d sent=%d errors=%d",
            processed,
            sent,
            errors,
        )
        return {"processed": processed, "sent": sent, "errors": errors}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _process_single_followup(self, followup: Dict[str, Any]) -> None:
        """Process a single follow-up entry."""
        tenant_id = str(followup["tenant_id"])
        session_id = followup["session_id"]
        follow_up_number = followup["follow_up_number"]
        followup_id = followup["id"]

        # 1. Get tenant config
        tenant = await self._get_tenant_config(tenant_id)
        if not tenant:
            raise ValueError(f"Tenant {tenant_id} not found")

        # 2. Get agent follow-up prompt from Supabase
        prompt_template = await self._get_followup_prompt(
            tenant_id, followup["agent_type"], follow_up_number
        )

        # 3. Generate follow-up message using LLM
        persona = tenant.get("agent_persona", "")
        message = await self._generate_followup_message(
            prompt_template=prompt_template,
            conversation_context=f"Session: {session_id}, Follow-up #{follow_up_number}",
            persona=persona,
        )

        # 4. Send via Helena API
        await self._send_followup_via_helena(tenant, session_id, message)

        # 5. Mark as 'sent'
        pool = await get_postgres_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                f"UPDATE {QUEUE_TABLE} SET status = 'sent' WHERE id = $1",
                followup_id,
            )

        # 6/7. Schedule next or conclude
        if follow_up_number < 3:
            await self._schedule_next_followup(followup, tenant)
        else:
            # Follow-up 3: conclude attendance
            helena_token = tenant.get("helena_api_token", "")
            if helena_token:
                async with HelenaClient(api_token=helena_token) as helena:
                    await helena.complete_session(session_id)
                logger.info("Session %s completed after follow-up 3", session_id)

            # Clean memory
            await self.memory_service.cleanup_session_memory(tenant_id, session_id)

            # Record event
            await self._record_event(
                tenant_id=tenant_id,
                event_type="attendance_completed",
                context={
                    "session_id": session_id,
                    "reason": "follow_up_timeout",
                    "phone_number": followup["phone_number"],
                },
            )

    async def _schedule_next_followup(
        self,
        current: Dict[str, Any],
        tenant: Dict[str, Any],
    ) -> None:
        """Schedule the next follow-up after the current one was sent."""
        next_number = current["follow_up_number"] + 1
        delay_key = f"followup_{next_number}_minutes"
        delay_minutes = tenant.get(delay_key, 60)

        scheduled_at = datetime.now(SP_TZ) + timedelta(minutes=delay_minutes)

        pool = await get_postgres_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                f"""
                INSERT INTO {QUEUE_TABLE}
                    (tenant_id, session_id, phone_number, agent_type,
                     follow_up_number, scheduled_at, status)
                VALUES ($1, $2, $3, $4, $5, $6, 'pending')
                """,
                str(current["tenant_id"]),
                current["session_id"],
                current["phone_number"],
                current["agent_type"],
                next_number,
                scheduled_at,
            )

        logger.info(
            "Scheduled follow-up %d for session=%s at %s",
            next_number,
            current["session_id"],
            scheduled_at.isoformat(),
        )

    async def _get_tenant_config(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Fetch tenant config from Supabase RDG."""
        sb = get_supabase_client()
        result = sb.table(TENANTS_TABLE).select("*").eq("id", tenant_id).execute()
        if result.data:
            return result.data[0]
        return None

    async def _get_followup_prompt(
        self,
        tenant_id: str,
        agent_type: str,
        followup_number: int,
    ) -> str:
        """Fetch the follow-up prompt template from Supabase RDG.

        Looks up by agent_id (resolved from tenant + agent_type) and followup_number.
        Falls back to a sensible default if not configured.
        """
        sb = get_supabase_client()

        # Resolve agent_id from tenant agents
        agent_result = (
            sb.table("agentpolitico_tenant_agents")
            .select("id")
            .eq("tenant_id", tenant_id)
            .eq("agent_type", agent_type)
            .eq("active", True)
            .limit(1)
            .execute()
        )
        if not agent_result.data:
            return self._default_followup_prompt(followup_number)

        agent_id = agent_result.data[0]["id"]

        prompt_result = (
            sb.table(PROMPTS_TABLE)
            .select("prompt_template")
            .eq("agent_id", agent_id)
            .eq("followup_number", followup_number)
            .eq("active", True)
            .execute()
        )
        if prompt_result.data:
            return prompt_result.data[0]["prompt_template"]

        return self._default_followup_prompt(followup_number)

    @staticmethod
    def _default_followup_prompt(followup_number: int) -> str:
        """Return a default follow-up prompt when none is configured."""
        defaults = {
            1: (
                "O cidadao parou de responder. Envie uma mensagem gentil "
                "perguntando se ele ainda precisa de ajuda."
            ),
            2: (
                "O cidadao continua sem responder. Envie uma segunda mensagem "
                "reforçando que estamos a disposicao."
            ),
            3: (
                "Ultima tentativa de contato. Informe que o atendimento sera "
                "encerrado caso nao haja resposta."
            ),
        }
        return defaults.get(followup_number, defaults[1])

    async def _generate_followup_message(
        self,
        prompt_template: str,
        conversation_context: str,
        persona: str,
    ) -> str:
        """Use LLM (Grok via LangChain) to generate a contextual follow-up message."""
        llm = ChatOpenAI(
            model=settings.GROK_MODEL,
            api_key=settings.GROK_API_KEY,
            base_url=settings.GROK_BASE_URL,
            temperature=0.7,
        )

        system_content = (
            f"Voce e um assistente de gabinete parlamentar.\n"
            f"Persona: {persona}\n\n"
            f"Gere uma mensagem de follow-up curta e natural para WhatsApp. "
            f"Nao use markdown. Nao use emojis em excesso. Seja cordial e direto."
        )

        human_content = (
            f"Instrucao de follow-up: {prompt_template}\n\n"
            f"Contexto da conversa: {conversation_context}\n\n"
            f"Gere apenas o texto da mensagem, sem explicacoes adicionais."
        )

        response = await llm.ainvoke([
            SystemMessage(content=system_content),
            HumanMessage(content=human_content),
        ])

        return response.content.strip()

    async def _send_followup_via_helena(
        self,
        tenant: Dict[str, Any],
        session_id: str,
        message: str,
    ) -> None:
        """Send a follow-up message via Helena API."""
        helena_token = tenant.get("helena_api_token", "")
        if not helena_token:
            raise ValueError(
                f"Tenant {tenant.get('id')} has no helena_api_token configured"
            )

        async with HelenaClient(api_token=helena_token) as helena:
            await helena.send_message(session_id, message)

        logger.debug("Follow-up sent via Helena for session %s", session_id)

    async def _record_event(
        self,
        tenant_id: str,
        event_type: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a tenant event in Supabase RDG (best-effort)."""
        try:
            sb = get_supabase_client()
            sb.table(EVENTS_TABLE).insert({
                "tenant_id": tenant_id,
                "event_type": event_type,
                "context": context or {},
            }).execute()
        except Exception as e:
            logger.warning("Failed to record event %s: %s", event_type, e)
