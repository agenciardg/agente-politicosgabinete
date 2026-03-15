"""
LangGraph Nodes - Multi-Tenant Agent
======================================
Nodes for each step of the conversation flow.
Uses dynamic config from state (loaded from Supabase) instead of hardcoded values.

IMPORTANT: Each node returns ONLY the changed fields (partial dict).
LangGraph merges automatically with the checkpoint state.
NEVER mutate state directly.
"""

import re
import json
import logging
from typing import Literal, Dict, Any
from datetime import datetime, timedelta

import pytz
import httpx
from langchain_core.messages import AIMessage, HumanMessage

from src.agent.state import AgentState
from src.agent.prompts import (
    get_system_prompt,
    build_etapa1_context,
    build_etapa2_context,
    format_classification_prompt,
    build_transfer_farewell_prompt,
)
from src.services.grok_client import get_grok_llm
from src.services.helena_client import HelenaClient

logger = logging.getLogger(__name__)


# =====================================================
# HELPERS
# =====================================================

def _get_latest_human_message(state: AgentState) -> str:
    """Return the content of the latest human message."""
    for msg in reversed(state.get("messages", [])):
        if hasattr(msg, "type") and msg.type == "human":
            return msg.content
    return ""


def _classify_confirmation_response(text: str) -> str:
    """
    Classify citizen response to data summary:
    - "confirmed": explicit confirmation
    - "rejected": wants to correct
    - "indeterminate": neither confirmation nor rejection
    """
    text_lower = text.strip().lower()

    confirmation_phrases = [
        "sim", "ok", "correto", "certo", "isso", "confirmo",
        "tá certo", "ta certo", "está certo", "esta certo",
        "tudo certo", "pode salvar", "isso mesmo", "exato",
        "perfeito", "tá correto", "ta correto", "está correto",
        "esta correto", "pode confirmar", "confirma", "confirmado",
        "tá tudo certo", "ta tudo certo", "tudo correto",
        "são esses", "sao esses", "é isso", "e isso",
        "tá ok", "ta ok", "tá bom", "ta bom",
    ]
    if text_lower in {"sim", "s", "ok", "ss", "sím", "si", "yes", "y"}:
        return "confirmed"
    for phrase in confirmation_phrases:
        if phrase in text_lower:
            return "confirmed"

    rejection_phrases = [
        "errado", "incorreto", "não está", "nao esta",
        "tá errado", "ta errado", "está errado", "esta errado",
        "preciso corrigir", "tem erro", "corrija", "corrige",
        "na verdade", "tá incorreto", "ta incorreto",
        "não é isso", "nao e isso", "não tá certo", "nao ta certo",
        "quero mudar", "quero corrigir", "preciso mudar",
    ]
    for phrase in rejection_phrases:
        if phrase in text_lower:
            return "rejected"

    if text_lower in {"não", "nao", "n"}:
        return "rejected"

    return "indeterminate"


def _get_helena_client(state: AgentState) -> HelenaClient:
    """Create a HelenaClient using the tenant's API token from state."""
    tenant_config = state.get("tenant_config") or {}
    api_token = tenant_config.get("helena_api_token", "")
    base_url = tenant_config.get("helena_base_url", "https://api.helena.run")

    if not api_token:
        from src.config.settings import settings
        api_token = settings.HELENA_API_TOKEN

    return HelenaClient(api_token=api_token, base_url=base_url)


def _get_tenant_llm(state: AgentState):
    """Get LLM instance configured for the tenant."""
    from src.config.settings import settings

    tenant_config = state.get("tenant_config") or {}
    return get_grok_llm(
        api_key=tenant_config.get("llm_api_key") or settings.GROK_API_KEY,
        model=tenant_config.get("llm_model") or settings.GROK_MODEL,
    )


def _get_required_field_keys(state: AgentState) -> list:
    """Get list of required field keys from tenant config."""
    active_fields = state.get("active_fields") or []
    if active_fields:
        return [f.get("helena_field_key", "") for f in active_fields if f.get("helena_field_key")]

    # Default fields
    return [
        "email", "data-nascimento", "endereco", "bairro",
        "cep", "cidade", "estado", "cpf",
    ]


def _resolve_field_value(
    storage_instruction: str,
    field_name: str,
    classification: dict,
    contact_data: dict,
    custom_fields: dict,
) -> str:
    """Resolve a field value based on storage_instruction and field_name.

    Uses keyword matching on the instruction and field name to find the
    right data source from classification results or contact data.
    """
    instruction_lower = (storage_instruction or "").lower()
    field_lower = (field_name or "").lower()

    # Keyword mapping: (keywords in instruction or field_name) -> value source
    keyword_map = [
        # Classification-based fields
        (["solicitacao", "solicitação", "tipo"], lambda: classification.get("tipo_solicitacao", "")),
        (["resumo breve", "resumo curto", "manifestacao", "manifestação"], lambda: classification.get("resumo_curto", "")),
        (["descricao", "descrição", "resumo longo", "resumo completo", "detalhad"], lambda: classification.get("resumo_longo", "")),
        (["urgencia", "urgência", "prioridade"], lambda: classification.get("urgencia", "")),
        (["equipe", "categoria", "area", "área"], lambda: classification.get("equipe", "")),
        # Contact-based fields
        (["nome completo", "nome"], lambda: contact_data.get("name", "")),
        (["email", "e-mail"], lambda: contact_data.get("email", "")),
        (["cpf"], lambda: custom_fields.get("cpf", "")),
        (["nascimento", "data de nascimento", "data nascimento"], lambda: custom_fields.get("data-nascimento", "")),
        (["cep"], lambda: custom_fields.get("cep", "")),
        (["endereco", "endereço", "logradouro", "rua"], lambda: custom_fields.get("endereco", "") or custom_fields.get("endere-o", "")),
        (["bairro"], lambda: custom_fields.get("bairro", "")),
        (["cidade", "municipio", "município"], lambda: custom_fields.get("cidade", "")),
        (["estado", "uf"], lambda: custom_fields.get("estado", "")),
        (["privacidade", "politica", "política", "lgpd"], lambda: "Identificado na tag do contato"),
        (["data cadastro", "data_cadastro"], lambda: custom_fields.get("data-cadastro", "")),
    ]

    combined = f"{instruction_lower} {field_lower}"
    for keywords, value_fn in keyword_map:
        if any(kw in combined for kw in keywords):
            return value_fn()

    return ""


def _extract_cep_from_text(text: str):
    """Extract CEP from text using regex."""
    match = re.search(r"\b(\d{5})-?(\d{3})\b", text)
    if match:
        return match.group(1) + match.group(2)
    return None


async def _lookup_cep(cep: str) -> dict:
    """Lookup address from CEP via ViaCEP API."""
    cep_clean = re.sub(r"[^0-9]", "", cep)
    if len(cep_clean) != 8:
        return {"found": False, "error": "CEP invalido (deve ter 8 digitos)"}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            url = f"https://viacep.com.br/ws/{cep_clean}/json/"
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

        if data.get("erro"):
            return {"found": False, "error": "CEP nao encontrado"}

        return {
            "found": True,
            "cep": cep_clean,
            "endereco": data.get("logradouro", ""),
            "complemento": data.get("complemento", ""),
            "bairro": data.get("bairro", ""),
            "cidade": data.get("localidade", ""),
            "estado": data.get("uf", ""),
        }
    except Exception as e:
        logger.error(f"Erro ao consultar CEP {cep_clean}: {e}")
        return {"found": False, "error": str(e)}


async def _save_contact_to_helena(
    state: AgentState,
    collected_data: dict,
) -> Dict[str, Any]:
    """Save collected contact data to Helena CRM. Returns state updates."""
    updates: Dict[str, Any] = {}
    helena_client = _get_helena_client(state)

    try:
        custom_fields = {}
        field_map = {
            "cpf": "cpf",
            "data_nascimento": "data-nascimento",
            "cep": "cep",
            "endereco": "endereco",
            "bairro": "bairro",
            "cidade": "cidade",
            "estado": "estado",
        }

        for data_key, helena_key in field_map.items():
            value = collected_data.get(data_key)
            if value:
                custom_fields[helena_key] = value

        # Add data-cadastro if not existing (NEVER overwrite)
        existing_data_cadastro = (
            (state.get("contact_data") or {})
            .get("customFields", {})
            .get("data-cadastro")
        )
        if not existing_data_cadastro:
            tenant_config = state.get("tenant_config") or {}
            timezone = tenant_config.get("timezone", "America/Sao_Paulo")
            tz = pytz.timezone(timezone)
            custom_fields["data-cadastro"] = datetime.now(tz).strftime("%d/%m/%Y")

        # Build update payload
        update_data: Dict[str, Any] = {}
        if collected_data.get("name"):
            update_data["name"] = collected_data["name"]
        if collected_data.get("email"):
            update_data["email"] = collected_data["email"]
        if custom_fields:
            update_data["customFields"] = custom_fields

        await helena_client.update_contact(
            phone=state["phone_number"],
            data=update_data,
        )

        logger.info(f"Contact updated in Helena for {state.get('phone_number')} (tenant={state.get('tenant_id')})")

        # Update contact_data in state
        updated_contact = dict(state.get("contact_data") or {})
        if collected_data.get("name"):
            updated_contact["name"] = collected_data["name"]
        if collected_data.get("email"):
            updated_contact["email"] = collected_data["email"]
        updated_cf = dict(updated_contact.get("customFields", {}))
        for data_key, helena_key in field_map.items():
            value = collected_data.get(data_key)
            if value:
                updated_cf[helena_key] = value
        if "data-cadastro" in custom_fields:
            updated_cf["data-cadastro"] = custom_fields["data-cadastro"]
        updated_contact["customFields"] = updated_cf

        updates["contact_data"] = updated_contact
        updates["data_saved"] = True
        updates["data_collected"] = True
        updates["current_phase"] = "ETAPA_2"
        updates["awaiting_confirmation"] = False
        updates["demand_asked"] = True

    except Exception as e:
        logger.error(f"Error saving contact to Helena: {e}", exc_info=True)
        updates["error"] = f"Erro ao salvar dados: {str(e)}"
    finally:
        await helena_client.close()

    return updates


# =====================================================
# NODE: VALIDATE DATA (ETAPA 1)
# =====================================================

async def validate_data_node(state: AgentState) -> Dict[str, Any]:
    """
    Node for contact data validation (ETAPA 1).

    Multi-tenant:
    - Uses tenant's Helena API token
    - Uses tenant's active_fields for required field validation
    - Detects CEP in user message and does ViaCEP lookup
    - Processes pending data confirmation
    """
    updates: Dict[str, Any] = {}

    if not state.get("current_phase"):
        updates["current_phase"] = "ETAPA_1"

    if state.get("data_saved") or state.get("data_collected"):
        return updates

    required_fields = _get_required_field_keys(state)

    # ---- Process pending confirmation from previous turn ----
    if state.get("awaiting_confirmation") and state.get("pending_data"):
        latest_msg = _get_latest_human_message(state)
        response_type = _classify_confirmation_response(latest_msg)

        if response_type == "rejected":
            logger.info(
                f"Citizen rejected data summary for {state.get('phone_number')} "
                f"(tenant={state.get('tenant_id')})"
            )
            updates["awaiting_confirmation"] = False
            updates["pending_data"] = None
            return updates

        if response_type == "indeterminate":
            logger.info(
                f"Indeterminate response for {state.get('phone_number')} "
                f"(tenant={state.get('tenant_id')}) - maintaining flow"
            )
            updates["awaiting_confirmation"] = False
            updates["pending_data"] = None
            return updates

        # confirmed -> save to Helena
        logger.info(
            f"Citizen confirmed data for {state.get('phone_number')} "
            f"(tenant={state.get('tenant_id')}) - saving to Helena"
        )
        save_updates = await _save_contact_to_helena(state, state["pending_data"])
        return save_updates

    # ---- Fetch contact from Helena if not already loaded ----
    if not state.get("contact_data"):
        helena_client = _get_helena_client(state)
        try:
            try:
                contact = await helena_client.get_contact_by_phone(state["phone_number"])
            except httpx.HTTPStatusError as http_err:
                status_code = http_err.response.status_code
                response_text = ""
                try:
                    response_text = http_err.response.text
                except Exception:
                    pass

                logger.warning(
                    f"Helena API returned HTTP {status_code} for "
                    f"phone={state['phone_number']} (tenant={state.get('tenant_id')})"
                )

                is_not_found = (
                    status_code == 404
                    or (status_code == 500 and "não encontrado" in response_text.lower())
                )

                if is_not_found:
                    logger.info(f"Contact not found for {state['phone_number']} - treating as new contact")
                    updates["contact_data"] = {}
                    updates["contact_name"] = ""
                    updates["contact_id"] = ""
                    updates["validation_status"] = "incomplete"
                    updates["missing_fields"] = list(required_fields)
                    updates["current_phase"] = "ETAPA_1"
                    return updates
                raise

            # Contact found - check for missing fields
            logger.info(
                f"Helena returned contact for phone={state['phone_number']} - "
                f"name={contact.get('name', 'N/A')}, id={contact.get('id', 'N/A')}"
            )

            cf = contact.get("customFields") or {}
            _helena_key_aliases = {
                "endereco": ["endereco", "endere-o", "endereço"],
            }

            def _get_cf_value(field_name: str):
                aliases = _helena_key_aliases.get(field_name, [field_name])
                for alias in aliases:
                    val = cf.get(alias)
                    if val:
                        return val
                return None

            missing_fields = []
            for field in required_fields:
                if field == "email":
                    value = contact.get("email")
                else:
                    value = _get_cf_value(field)

                is_empty = not value or (isinstance(value, str) and value.strip().lower() in (
                    "", "-", "—", "n/a", "vazio", "nenhum", "não informado",
                    "não informou", "não possui", "nao informado", "nao informou",
                ))
                if is_empty:
                    missing_fields.append(field)

            updates["contact_data"] = contact
            updates["contact_name"] = contact.get("name", "")
            updates["contact_id"] = contact.get("id", "")

            if not missing_fields:
                updates["validation_status"] = "complete"
                updates["data_collected"] = True
                updates["current_phase"] = "ETAPA_2"
                logger.info(f"All data complete for {state['phone_number']}")
            else:
                updates["validation_status"] = "incomplete"
                updates["missing_fields"] = missing_fields
                updates["current_phase"] = "ETAPA_1"
                logger.info(f"Missing fields for {state['phone_number']}: {missing_fields}")

        except Exception as e:
            logger.error(
                f"Exception fetching contact for {state['phone_number']} "
                f"(tenant={state.get('tenant_id')}): {e}",
                exc_info=True,
            )
            updates["contact_data"] = {}
            updates["contact_name"] = ""
            updates["contact_id"] = ""
            updates["validation_status"] = "error"
            updates["missing_fields"] = list(required_fields)
            updates["current_phase"] = "ETAPA_1"
            updates["error"] = str(e)
        finally:
            await helena_client.close()

    # ---- Detect CEP in latest message ----
    latest_msg = _get_latest_human_message(state)
    if latest_msg and not state.get("cep_lookup_result"):
        cep = _extract_cep_from_text(latest_msg)
        if cep:
            logger.info(f"CEP detected in message: {cep}")
            cep_result = await _lookup_cep(cep)
            updates["cep_lookup_result"] = cep_result

    return updates


# =====================================================
# NODE: AGENT (CONVERSATION WITH LLM)
# =====================================================

async def agent_node(state: AgentState) -> Dict[str, Any]:
    """
    Main agent node - conversation with tenant-specific LLM.
    Injects dynamic context based on current state and tenant config.
    """
    llm = _get_tenant_llm(state)

    contact_name = state.get("contact_name", "")
    agent_config = state.get("agent_config") or {}
    tenant_config = state.get("tenant_config") or {}
    active_panels = state.get("active_panels") or []
    active_fields = state.get("active_fields") or []

    # Build system prompt from tenant config
    system_prompt = get_system_prompt(
        contact_name=contact_name,
        agent_config=agent_config,
        tenant_config=tenant_config,
        active_panels=active_panels,
    )

    updates: Dict[str, Any] = {"demand_ready": False}

    # ---- Load long-term memory for context ----
    memory_context = ""
    try:
        from src.services.memory_service import MemoryService

        memory_svc = MemoryService()
        citizen_memory = await memory_svc.get_citizen_memory(
            tenant_id=state.get("tenant_id", ""),
            phone_number=state.get("phone_number", ""),
        )
        if citizen_memory:
            total = citizen_memory.get("total_contacts", 0)
            last_cat = citizen_memory.get("last_category", "")
            last_content = citizen_memory.get("content", "")
            last_date = citizen_memory.get("updated_at", "")
            memory_context = (
                f"## HISTORICO DO CIDADAO\n\n"
                f"Este cidadao ja entrou em contato {total} vez(es) anteriormente.\n"
                f"Ultimo atendimento: {last_content}\n"
                f"Categoria: {last_cat}\n"
                f"Data: {last_date}\n\n"
                f"Use essa informacao para personalizar o atendimento. "
                f"Mencione brevemente que ja conversaram antes, se apropriado."
            )
    except Exception as e:
        logger.warning(f"Error loading citizen memory: {e}")

    # ---- Build dynamic context based on phase ----
    context_parts = []
    if memory_context:
        context_parts.append(memory_context)
    current_phase = state.get("current_phase", "ETAPA_1")

    if current_phase == "ETAPA_1" and not state.get("data_collected"):
        missing = state.get("missing_fields", [])
        contact_data = state.get("contact_data") or {}

        # Safety guard
        if not missing and not state.get("data_collected"):
            missing = _get_required_field_keys(state)
            logger.warning(
                f"agent_node: ETAPA_1 with empty missing_fields for "
                f"{state.get('phone_number')} - defaulting to all required fields"
            )

        if missing:
            etapa1_block = build_etapa1_context(
                missing_fields=missing,
                contact_name=contact_name,
                contact_data=contact_data,
                insistence_count=state.get("insistence_count") or 0,
                cep_lookup_result=state.get("cep_lookup_result"),
                active_fields=active_fields or None,
                agent_config=agent_config or None,
            )
            context_parts.append(etapa1_block)
        else:
            context_parts.append(
                "FASE ATUAL: Dados cadastrais completos. Pergunte como pode ajudar o cidadao."
            )

    elif current_phase == "ETAPA_2" or (
        current_phase == "ETAPA_1" and state.get("data_collected")
    ):
        etapa2_block = build_etapa2_context(
            contact_name=contact_name,
            etapa2_turns=state.get("etapa2_turns") or 0,
            active_panels=active_panels or None,
            agent_config=agent_config or None,
        )
        context_parts.append(etapa2_block)

    # Append dynamic context to system prompt
    if context_parts:
        dynamic_context = "\n".join(context_parts)
        system_prompt += f"\n\n---\n\n## CONTEXTO DA CONVERSA ATUAL\n\n{dynamic_context}"

    # Build messages for LLM
    messages = [{"role": "system", "content": system_prompt}]
    for msg in state["messages"]:
        if hasattr(msg, "type"):
            if msg.type == "human":
                messages.append({"role": "user", "content": msg.content})
            elif msg.type == "ai":
                messages.append({"role": "assistant", "content": msg.content})

    response = await llm.ainvoke(messages)
    updates["messages"] = [AIMessage(content=response.content)]

    # Increment ETAPA 2 turn counter
    if current_phase == "ETAPA_2" or (
        current_phase == "ETAPA_1" and state.get("data_collected")
    ):
        current_turns = state.get("etapa2_turns") or 0
        updates["etapa2_turns"] = current_turns + 1
        if not state.get("demand_asked"):
            updates["demand_asked"] = True

    return updates


# =====================================================
# NODE: POST PROCESS
# =====================================================

async def post_process_node(state: AgentState) -> Dict[str, Any]:
    """
    Post-processing of agent response.
    Detects and processes markers in AI response.

    Multi-tenant: uses tenant's Helena client for CRM operations.
    """
    updates: Dict[str, Any] = {}

    latest_ai = None
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, AIMessage):
            latest_ai = msg
            break

    if not latest_ai:
        return updates

    content = latest_ai.content
    message_modified = False

    # ====================================================
    # MARKER 1: [DADOS_CONFIRMADOS] (ETAPA 1)
    # ====================================================
    dados_pattern = r"[\[*]*DADOS_CONFIRMADOS[\]*]*\s*(\{[^}]+\})\s*(?:[\[*]*/?\s*DADOS_CONFIRMADOS[\]*]*)?"
    dados_match = re.search(dados_pattern, content, re.DOTALL)

    if dados_match:
        logger.info(f"DADOS_CONFIRMADOS marker detected for {state.get('phone_number')}")

        try:
            json_str = dados_match.group(1).strip()
            collected_data = json.loads(json_str)
            logger.info(f"Data extracted: {list(collected_data.keys())}")

            # Normalize email
            _email = collected_data.get("email", "")
            _refused_markers = {"não quis informar", "nao quis informar", "vazio", ""}
            if not _email or _email.strip().lower() in _refused_markers:
                collected_data["email"] = "naoinformou@email.com"

            # Decision: confirm or save directly?
            total_missing = len(state.get("missing_fields", []))

            if total_missing <= 3:
                # Few fields -> save directly
                logger.info(
                    f"Auto-save: {total_missing} missing fields (<=3) "
                    f"for {state.get('phone_number')} - saving directly"
                )
                save_updates = await _save_contact_to_helena(state, collected_data)
                updates.update(save_updates)
            else:
                # Many fields -> ask for confirmation
                updates["pending_data"] = collected_data
                updates["awaiting_confirmation"] = True
                logger.info(
                    f"Pending data for {state.get('phone_number')} "
                    f"({total_missing} fields) - awaiting confirmation"
                )

        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error in DADOS_CONFIRMADOS: {e}")

        # Remove marker from content
        content = re.sub(
            r"[\[*]*DADOS_CONFIRMADOS[\]*]*\s*\{[^}]+\}\s*(?:[\[*]*/?\s*DADOS_CONFIRMADOS[\]*]*)?",
            "", content, flags=re.DOTALL
        ).strip()
        message_modified = True

    # ====================================================
    # MARKER 2: [CLASSIFICAR_DEMANDA] (ETAPA 2)
    # ====================================================
    classify_pattern = r"\[CLASSIFICAR_DEMANDA\]"
    classify_match = re.search(classify_pattern, content)

    if classify_match:
        logger.info(f"CLASSIFICAR_DEMANDA marker detected for {state.get('phone_number')}")
        updates["demand_ready"] = True
        content = re.sub(classify_pattern, "", content).strip()
        message_modified = True

    # ====================================================
    # MARKER 3: [RECUSA_DADOS] (ETAPA 1 -- citizen refused all)
    # ====================================================
    recusa_pattern = r"\[RECUSA_DADOS\]"
    recusa_match = re.search(recusa_pattern, content)

    if recusa_match:
        logger.info(f"RECUSA_DADOS marker detected for {state.get('phone_number')}")
        updates["refused_all_data"] = True

        # Write "Nao aceitou identificar" to Helena contact
        try:
            helena_client = _get_helena_client(state)
            contact_id = state.get("contact_id", "")
            if contact_id:
                await helena_client.update_contact(
                    phone=state["phone_number"],
                    data={"customFields": {"observacoes": "Nao aceitou identificar"}},
                )
                logger.info(f"Refusal noted in Helena for contact {contact_id}")
            await helena_client.close()
        except Exception as e:
            logger.error(f"Error recording data refusal in Helena: {e}")

        updates["data_collected"] = True
        updates["current_phase"] = "ETAPA_2"
        content = re.sub(recusa_pattern, "", content).strip()
        message_modified = True

    # ====================================================
    # INSISTENCE COUNTER
    # ====================================================
    insistence_phrase = "esses dados ajudam a agilizar o atendimento"
    if insistence_phrase in latest_ai.content.lower():
        current_count = state.get("insistence_count") or 0
        max_insistence = state.get("max_insistence") or 2
        if current_count < max_insistence:
            updates["insistence_count"] = current_count + 1
            logger.info(
                f"Insistence detected for {state.get('phone_number')}: "
                f"count now {current_count + 1}/{max_insistence}"
            )

    # ====================================================
    # FINAL SANITIZATION -- catch-all for leaked markers
    # ====================================================
    for marker in ["DADOS_CONFIRMADOS", "CLASSIFICAR_DEMANDA", "RECUSA_DADOS"]:
        if marker in content:
            content = re.sub(
                rf"[\[*]*{marker}[\]*]*\s*(?:\{{[^}}]*\}})?\s*(?:[\[*]*/?\s*{marker}[\]*]*)?",
                "", content, flags=re.DOTALL
            ).strip()
            message_modified = True
            logger.warning(
                f"Catch-all sanitization: marker {marker} removed for {state.get('phone_number')}"
            )

    if message_modified:
        updates["messages"] = [AIMessage(content=content, id=latest_ai.id)]

    return updates


# =====================================================
# ROUTER: POST PROCESS
# =====================================================

def post_process_router(state: AgentState) -> Literal["classify", "end"]:
    """Router after post_process: classify if demand_ready, else END."""
    if state.get("demand_ready") and not state.get("demand_classified"):
        logger.info("Post-process router: demand_ready=True -> classify")
        return "classify"
    return "end"


# =====================================================
# NODE: CLASSIFY DEMAND (ETAPA 2)
# =====================================================

async def classify_demand_node(state: AgentState) -> Dict[str, Any]:
    """
    Node to classify the demand (ETAPA 2).

    Multi-tenant: uses tenant's panel categories and LLM config.
    """
    llm = _get_tenant_llm(state)
    active_panels = state.get("active_panels") or []
    agent_config = state.get("agent_config") or {}
    agent_name = agent_config.get("agent_name", "Assistente")

    # Format conversation history
    formatted = []
    for msg in state["messages"]:
        if isinstance(msg, HumanMessage):
            formatted.append(f"Cidadao: {msg.content}")
        elif isinstance(msg, AIMessage):
            formatted.append(f"{agent_name}: {msg.content}")
    conversation_text = "\n".join(formatted)

    # Build classification prompt with tenant's panels
    prompt = format_classification_prompt(
        conversation_history=conversation_text,
        active_panels=active_panels or None,
    )

    try:
        response = await llm.ainvoke(prompt)
        content = response.content

        # Extract JSON
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            json_str = content.split("```")[1].split("```")[0].strip()
        else:
            json_str = content.strip()

        classification = json.loads(json_str)

        # Validate category against configured panels
        if active_panels:
            valid_categories = [p.get("panel_name", "") for p in active_panels]
            if classification.get("equipe") not in valid_categories:
                # Try to find a matching panel by partial match
                equipe = classification.get("equipe", "")
                matched = False
                for panel_name in valid_categories:
                    if equipe.lower() in panel_name.lower() or panel_name.lower() in equipe.lower():
                        classification["equipe"] = panel_name
                        matched = True
                        break
                if not matched:
                    classification["equipe"] = "atendimento_geral"

        # Validate urgency
        if classification.get("urgencia") not in ("baixa", "media", "alta"):
            classification["urgencia"] = "media"

        # Ensure required fields
        for field in ["equipe", "solicitacao", "tipo_solicitacao",
                      "descricao", "resumo_longo", "resumo_curto", "urgencia"]:
            if field not in classification:
                classification[field] = ""

        logger.info(
            f"Classification for {state.get('phone_number')}: "
            f"equipe={classification.get('equipe')}, urgencia={classification.get('urgencia')}"
        )

    except Exception as e:
        logger.error(f"Classification error: {e}", exc_info=True)
        classification = {
            "equipe": "atendimento_geral",
            "solicitacao": "Atendimento Geral",
            "tipo_solicitacao": "Erro na Classificacao",
            "descricao": f"Erro durante classificacao: {str(e)}",
            "resumo_longo": "Erro ao processar. Encaminhada para atendimento geral.",
            "resumo_curto": "Erro na classificacao",
            "urgencia": "media",
            "error": str(e),
        }

    return {
        "classification": classification,
        "category": classification.get("equipe", "atendimento_geral"),
        "urgency": classification.get("urgencia", "media"),
        "demand_classified": True,
        "current_phase": "ETAPA_3",
    }


# =====================================================
# NODE: TRANSFER (ETAPA 3)
# =====================================================

async def transfer_node(state: AgentState) -> Dict[str, Any]:
    """
    Node to transfer session and route card (ETAPA 3).

    Multi-tenant: uses tenant's panel config for routing.
    Looks up panel_id, step_id, department_id from active_panels.
    """
    category = state.get("category", "atendimento_geral")
    classification = state.get("classification") or {}
    contact_data = state.get("contact_data") or {}
    active_panels = state.get("active_panels") or []
    agent_config = state.get("agent_config") or {}
    tenant_config = state.get("tenant_config") or {}

    updates: Dict[str, Any] = {}

    try:
        # Find panel config for this category
        panel_config = None
        for panel in active_panels:
            if panel.get("panel_name", "") == category:
                panel_config = panel
                break

        # Fallback: try to find atendimento_geral
        if not panel_config:
            for panel in active_panels:
                if "geral" in panel.get("panel_name", "").lower():
                    panel_config = panel
                    break

        if not panel_config:
            raise ValueError(
                f"No panel config found for category '{category}' "
                f"(tenant={state.get('tenant_id')})"
            )

        panel_id = panel_config.get("helena_panel_id", "")
        step_id = panel_config.get("helena_step_id", "")
        department_id = panel_config.get("helena_department_id", "")

        helena_client = _get_helena_client(state)

        try:
            # 1. Transfer chat session to department
            if department_id:
                await helena_client.transfer_session(
                    session_id=state["session_id"],
                    department_id=department_id,
                )
                logger.info(
                    f"Session {state['session_id']} transferred to department {department_id}"
                )

            # 2. Get panel custom fields for card creation
            custom_fields_list = []
            if panel_id:
                custom_fields_list = await helena_client.get_panel_custom_fields(
                    panel_id=panel_id
                )

            # 3. Create field mapping {name: key}
            panel_field_mapping = {
                cf_item["name"]: cf_item["key"]
                for cf_item in custom_fields_list
                if "name" in cf_item and "key" in cf_item
            }

            # 4. Duplicate card to destination panel
            new_card_id = None
            if step_id and state.get("card_id"):
                new_card = await helena_client.duplicate_card(
                    card_id=state["card_id"],
                    step_id=step_id,
                )
                new_card_id = new_card.get("id")

            if not new_card_id:
                logger.warning("Card duplication did not return ID")

            # 5. Build custom fields data from field mappings
            custom_fields_data = {}
            cf = contact_data.get("customFields", {})

            # Map from tenant's field_mappings config
            field_mappings = panel_config.get("field_mappings", [])
            for mapping in field_mappings:
                helena_field_name = mapping.get("helena_field_name", "")
                storage_instruction = mapping.get("storage_instruction", "")
                if helena_field_name in panel_field_mapping:
                    field_key = panel_field_mapping[helena_field_name]
                    value = _resolve_field_value(
                        storage_instruction, helena_field_name,
                        classification, contact_data, cf
                    )
                    if value:
                        custom_fields_data[field_key] = value

            # Fallback: standard field mapping if no field_mappings configured
            if not field_mappings:
                standard_map = {
                    "Solicitacao": classification.get("tipo_solicitacao", ""),
                    "Data Cadastro": cf.get("data-cadastro", ""),
                    "Nome Completo": contact_data.get("name", ""),
                    "Politica Privacidade": "Identificado na tag do contato",
                    "Descricao Manifestacao": classification.get("resumo_longo", ""),
                    "Manifestacao": classification.get("resumo_curto", ""),
                    "CPF": cf.get("cpf", ""),
                    "Data Nascimento": cf.get("data-nascimento", ""),
                    "Email": contact_data.get("email", ""),
                    "CEP": cf.get("cep", ""),
                    "Endereco": cf.get("endereco", ""),
                    "Bairro": cf.get("bairro", ""),
                    "Cidade": cf.get("cidade", ""),
                    "Estado": cf.get("estado", ""),
                }
                for field_name, field_value in standard_map.items():
                    if field_name in panel_field_mapping and field_value:
                        custom_fields_data[panel_field_mapping[field_name]] = field_value

            # 6. Calculate due date (24 hours)
            tz = pytz.timezone(tenant_config.get("timezone", "America/Sao_Paulo"))
            due_date = datetime.now(tz) + timedelta(hours=24)

            # 7. Prepare tags
            category_tag = panel_config.get("panel_name", "")
            urgency_tag = classification.get("urgencia", "media")
            tag_names = [t for t in [category_tag, urgency_tag, "whatsapp"] if t]

            # 8. Update duplicated card
            if new_card_id:
                card_data: Dict[str, Any] = {
                    "title": contact_data.get("name", ""),
                    "description": classification.get("descricao", ""),
                    "contactIds": [contact_data.get("id")] if contact_data.get("id") else [],
                    "dueDate": due_date.isoformat(),
                    "tagNames": tag_names,
                }
                if custom_fields_data:
                    card_data["customFields"] = custom_fields_data

                await helena_client.update_card(
                    card_id=new_card_id,
                    data=card_data,
                )

            # 9. Add category tag to CONTACT
            phone = state.get("phone_number", "")
            if phone and category_tag:
                await helena_client.add_contact_tags(
                    phone=phone,
                    tags=[category_tag],
                )

            updates["transfer_status"] = "success"
            updates["new_card_id"] = new_card_id
            updates["transferred_to_department"] = department_id

        finally:
            await helena_client.close()

    except Exception as e:
        logger.error(f"Transfer error: {e}", exc_info=True)
        updates["transfer_status"] = "failed"
        updates["new_card_id"] = None
        updates["transferred_to_department"] = None
        updates["error"] = str(e)

    # Handle post-transfer
    if updates.get("transfer_status") == "success":
        updates["transferred"] = True
        updates["current_phase"] = "COMPLETED"
        updates["should_continue"] = False

        # Generate farewell message using LLM
        contact_name = state.get("contact_name", "cidadao")

        farewell_prompt = build_transfer_farewell_prompt(
            contact_name=contact_name,
            classification=classification,
            agent_config=agent_config,
            tenant_config=tenant_config,
        )

        try:
            llm = _get_tenant_llm(state)
            farewell_response = await llm.ainvoke([
                {"role": "system", "content": farewell_prompt},
            ])
            transfer_confirmation = farewell_response.content.strip()
            logger.info(f"Farewell message generated for {state['phone_number']}")
        except Exception as e:
            logger.error(f"Error generating farewell message: {e}")
            agent_name = agent_config.get("agent_name", "Assistente")
            transfer_confirmation = (
                f"*{contact_name}*, acabei de encaminhar seu atendimento "
                f"para nossa equipe. Eles vao te orientar e fazer o possivel "
                f"para tentar ajudar com essa situacao. Fique tranquilo(a)!"
            )

        updates["messages"] = [AIMessage(content=transfer_confirmation)]

        # Save interaction to long-term memory before cleaning checkpoints
        try:
            from src.services.memory_service import MemoryService

            memory_svc = MemoryService()
            await memory_svc.save_interaction_memory(
                tenant_id=state.get("tenant_id", ""),
                phone_number=state.get("phone_number", ""),
                contact_name=contact_name,
                session_id=state.get("session_id", ""),
                classification=classification,
                agent_type=state.get("agent_type", "principal"),
                transferred_to_department=updates.get("transferred_to_department", ""),
                new_card_id=updates.get("new_card_id", ""),
            )
        except Exception as e:
            logger.error(f"Error saving interaction memory: {e}", exc_info=True)

        # Clean up checkpoints for this session
        try:
            from src.agent.graph import get_pool

            pool = get_pool()
            if pool:
                thread_id = state["phone_number"]
                async with pool.connection() as conn:
                    await conn.execute(
                        "DELETE FROM checkpoint_writes WHERE thread_id = %s",
                        (thread_id,),
                    )
                    await conn.execute(
                        "DELETE FROM checkpoint_blobs WHERE thread_id = %s",
                        (thread_id,),
                    )
                    await conn.execute(
                        "DELETE FROM checkpoints WHERE thread_id = %s",
                        (thread_id,),
                    )
                logger.info(f"Checkpoints cleaned for {thread_id} after transfer")
        except Exception as e:
            logger.error(f"Error cleaning checkpoints for {state['phone_number']}: {e}")
    else:
        updates["should_continue"] = False

    return updates


# =====================================================
# ROUTER NODE
# =====================================================

def router_node(state: AgentState) -> Literal["agent", "classify", "transfer", "end"]:
    """
    Routing node - decides which node to execute next.

    Logic:
    - ETAPA_1 -> agent (collect data via conversation)
    - ETAPA_2 + classified -> transfer
    - ETAPA_2 + not classified -> agent
    - ETAPA_3 + transferred -> end
    - ETAPA_3 + not transferred -> transfer (retry)
    - COMPLETED -> end
    """
    current_phase = state.get("current_phase", "ETAPA_1")

    if current_phase == "ETAPA_1":
        return "agent"
    elif current_phase == "ETAPA_2":
        if state.get("demand_classified"):
            return "transfer"
        return "agent"
    elif current_phase == "ETAPA_3":
        if state.get("transferred"):
            return "end"
        return "transfer"
    elif current_phase == "COMPLETED":
        return "end"

    return "agent"


# =====================================================
# SHOULD CONTINUE (kept for compatibility)
# =====================================================

def should_continue_node(state: AgentState) -> Literal["continue", "end"]:
    """Decide whether to continue the loop or end."""
    if state.get("should_continue", True) and state.get("current_phase") != "COMPLETED":
        return "continue"
    return "end"
