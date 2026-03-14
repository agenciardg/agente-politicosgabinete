"""
Webhook endpoint for WhatsApp messages (multi-tenant).

Receives messages from n8n/Helena integration, resolves the tenant
from the URL slug, and processes through the tenant-specific LangGraph agent.

Sending pattern (same as original):
- Webhook sends response DIRECTLY to Helena via send-sync
- Returns already_sent=True so n8n does NOT re-send
"""

import asyncio
import logging
import time

from fastapi import APIRouter, Path
from langchain_core.messages import HumanMessage, AIMessage

from src.models.webhook import WebhookRequest, WebhookResponse
from src.services.helena_client import HelenaClient
from src.agent.config_loader import TenantConfigLoader
from src.agent.graph import get_agent_graph

logger = logging.getLogger(__name__)

router = APIRouter()

# Simple text-level dedup: block identical text from the same session within 30s.
_recent_messages: dict[tuple[str, str], float] = {}
_DEDUP_WINDOW = 30  # seconds

# Per-session lock: prevents concurrent processing of the same session.
_session_locks: dict[str, asyncio.Lock] = {}
_session_lock_meta_lock = asyncio.Lock()


async def _get_session_lock(session_id: str) -> asyncio.Lock:
    """Get or create a lock for a given session."""
    async with _session_lock_meta_lock:
        if session_id not in _session_locks:
            _session_locks[session_id] = asyncio.Lock()
        return _session_locks[session_id]


@router.post("/webhook/{tenant_slug}/whatsapp", response_model=WebhookResponse)
async def process_whatsapp_message(
    request: WebhookRequest,
    tenant_slug: str = Path(..., description="Tenant slug identifier"),
) -> WebhookResponse:
    """
    Process incoming WhatsApp message through tenant-specific LangGraph agent.

    Multi-tenant flow:
    1. Resolve tenant from slug
    2. Load tenant-specific agent config (prompts, panels, fields)
    3. Process through LangGraph
    4. Send response DIRECTLY to Helena (send-sync) using tenant's token
    5. Return already_sent=True to n8n
    """
    try:
        session_id = request.sessionID
        msg_text = request.mensagem.strip().lower()

        # --- Text-level dedup ---
        dedup_key = (session_id, msg_text)
        now = time.time()

        expired = [k for k, t in _recent_messages.items() if now - t > 300]
        for k in expired:
            del _recent_messages[k]

        if dedup_key in _recent_messages and (now - _recent_messages[dedup_key]) < _DEDUP_WINDOW:
            logger.warning(
                f"Duplicate text from {request.numero} (tenant={tenant_slug}), skipping"
            )
            return WebhookResponse(
                success=True,
                message="duplicate_skipped",
                session_id=session_id,
                current_phase="DEDUP",
                data_collected=False,
                category=None,
                transferred=False,
                already_sent=True,
                error=None,
                metadata={"dedup": True},
            )

        # --- Per-session lock ---
        session_lock = await _get_session_lock(session_id)
        if session_lock.locked():
            logger.warning(
                f"Session {session_id} already being processed (tenant={tenant_slug})"
            )
            return WebhookResponse(
                success=True,
                message="session_busy",
                session_id=session_id,
                current_phase="LOCKED",
                data_collected=False,
                category=None,
                transferred=False,
                already_sent=True,
                error=None,
                metadata={"session_locked": True},
            )

        async with session_lock:
            logger.info(
                f"Processing webhook for tenant={tenant_slug}, "
                f"session={session_id}, phone={request.numero}"
            )

            # 1. Load tenant + agent config from Supabase
            config_loader = TenantConfigLoader()
            full_config = await config_loader.load_full_agent_config(
                tenant_slug=tenant_slug,
                phone_number=request.numero,
            )

            tenant_config = full_config["tenant_config"]
            agent_config = full_config["agent_config"]
            agent_type = full_config["agent_type"]
            is_assessor = full_config["is_assessor"]
            active_panels = full_config["active_panels"]
            active_fields = full_config["active_fields"]
            field_mappings = full_config["field_mappings"]
            tenant_id = str(tenant_config["id"])

            logger.info(
                f"Tenant resolved: id={tenant_id}, agent_type={agent_type}, "
                f"panels={len(active_panels)}, fields={len(active_fields)}"
            )

            # 2. Get agent graph (singleton, tenant-agnostic structure)
            graph = await get_agent_graph()

            # 3. Invoke agent with tenant state
            config = {
                "configurable": {
                    "thread_id": session_id,
                    "checkpoint_ns": f"tenant_{tenant_slug}",
                }
            }
            input_state = {
                "messages": [HumanMessage(content=request.mensagem)],
                "session_id": session_id,
                "phone_number": request.numero,
                "card_id": request.card_id,
                "tenant_id": tenant_id,
                "agent_type": agent_type,
                "tenant_config": tenant_config,
                "agent_config": agent_config,
                "active_panels": active_panels,
                "active_fields": active_fields,
                "field_mappings": field_mappings,
                "is_assessor": is_assessor,
            }

            result = await graph.ainvoke(input_state, config=config)

            # 4. Extract response from result
            response_message = ""
            if result.get("messages"):
                for msg in reversed(result["messages"]):
                    if isinstance(msg, AIMessage):
                        response_message = msg.content
                        break

            if not response_message:
                response_message = "Desculpe, ocorreu um erro ao processar sua mensagem."

            # 5. Send response DIRECTLY to Helena via send-sync
            already_sent = False
            if response_message:
                try:
                    helena_token = tenant_config.get("helena_api_token", "")
                    helena_base_url = tenant_config.get(
                        "helena_base_url", "https://api.helena.run"
                    )
                    if helena_token:
                        helena_client = HelenaClient(
                            api_token=helena_token,
                            base_url=helena_base_url,
                        )
                        try:
                            await helena_client.send_message(
                                session_id=session_id,
                                message=response_message,
                            )
                            already_sent = True
                            logger.info(
                                f"Response sent to Helena for session {session_id}"
                            )
                        finally:
                            await helena_client.close()
                    else:
                        logger.warning(
                            f"No Helena token for tenant {tenant_slug} - "
                            f"cannot send message directly"
                        )
                except Exception as e:
                    logger.error(
                        f"Error sending message to Helena: {e}", exc_info=True
                    )

            # 6. Record dedup AFTER successful processing
            _recent_messages[dedup_key] = time.time()

            # 7. Build response
            return WebhookResponse(
                success=True,
                message=response_message,
                session_id=session_id,
                current_phase=result.get("current_phase", "ETAPA_1"),
                data_collected=result.get("data_collected", False),
                category=result.get("category"),
                transferred=result.get("transferred", False),
                already_sent=already_sent,
                error=result.get("error"),
                metadata={
                    "tenant_slug": tenant_slug,
                    "tenant_id": tenant_id,
                    "agent_type": agent_type,
                },
            )

    except ValueError as e:
        # Tenant not found or config error
        logger.error(
            f"Config error for tenant={tenant_slug}: {e}", exc_info=True
        )
        return WebhookResponse(
            success=False,
            message="Desculpe, ocorreu um erro de configuracao.",
            session_id=request.sessionID,
            current_phase="ERROR",
            data_collected=False,
            category=None,
            transferred=False,
            already_sent=False,
            error=str(e),
            metadata={"error_type": "config_error", "tenant_slug": tenant_slug},
        )

    except Exception as e:
        logger.error(
            f"Error processing webhook for tenant={tenant_slug}: {e}",
            exc_info=True,
        )

        return WebhookResponse(
            success=False,
            message="Desculpe, ocorreu um erro ao processar sua mensagem.",
            session_id=request.sessionID,
            current_phase="ERROR",
            data_collected=False,
            category=None,
            transferred=False,
            already_sent=False,
            error=str(e),
            metadata={"error_type": type(e).__name__},
        )


@router.post("/webhook/{tenant_slug}/test", response_model=WebhookResponse)
async def test_webhook(
    request: WebhookRequest,
    tenant_slug: str = Path(..., description="Tenant slug identifier"),
) -> WebhookResponse:
    """Test webhook endpoint without invoking the agent."""
    logger.info(f"Test webhook for tenant={tenant_slug}, session={request.sessionID}")

    return WebhookResponse(
        success=True,
        message=f"Teste recebido! Tenant: {tenant_slug}, Mensagem: {request.mensagem}",
        session_id=request.sessionID,
        current_phase="TEST",
        data_collected=False,
        category=None,
        transferred=False,
        already_sent=False,
        error=None,
        metadata={
            "test_mode": True,
            "tenant_slug": tenant_slug,
            "phone_number": request.numero,
            "card_id": request.card_id,
        },
    )
