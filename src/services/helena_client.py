"""
Helena CRM API Client (Multi-Tenant)
=====================================
Cliente HTTP assincrono para integracao com Helena CRM.
Cada instancia recebe um api_token especifico do tenant.
"""

import re
import asyncio
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Retry helpers
# ---------------------------------------------------------------------------

HTTP_TIMEOUT = 30  # seconds
HTTP_MAX_RETRIES = 3


def _is_retryable_http_error(exc: BaseException) -> bool:
    """
    Returns True only for errors worth retrying.
    404 is expected for new contacts -- never retry.
    Helena returns 500 for "Contato nao encontrado" -- also not retryable.
    429 (rate-limit) and 503 (service unavailable) ARE retryable.
    """
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        # Always retry rate-limit and service unavailable
        if status in (429, 503):
            return True
        # Never retry other client errors (4xx)
        if status < 500:
            return False
        # Helena bug: returns 500 for "contact not found"
        try:
            body = exc.response.text.lower()
            if "nao encontrado" in body or "não encontrado" in body:
                return False
        except Exception:
            pass
        # Retry genuine 5xx
        return True
    # Retry on network / transport errors
    return isinstance(exc, (httpx.TimeoutException, httpx.NetworkError))


# ---------------------------------------------------------------------------
# Helena endpoint templates
# ---------------------------------------------------------------------------

HELENA_ENDPOINTS = {
    # core
    "get_contact_by_phone": "/core/v1/contact/phonenumber/{phone}",
    "update_contact": "/core/v1/contact/phonenumber/{phone}",
    "add_contact_tags": "/core/v1/contact/phonenumber/{phone}/tags",
    "get_contact_custom_fields": "/core/v1/custom-field",
    # crm
    "get_panels": "/crm/v1/panel",
    "get_panel_steps": "/crm/v1/panel/{panel_id}/step",
    "get_panel_custom_fields": "/crm/v1/panel/{panel_id}/custom-fields",
    "duplicate_card": "/crm/v1/panel/card/{card_id}/duplicate",
    "update_card": "/crm/v1/panel/card/{card_id}",
    # chat
    "get_departments": "/chat/v1/department",
    "transfer_session": "/chat/v1/session/{session_id}/transfer",
    "complete_session": "/chat/v1/session/{session_id}/complete",
    "send_message": "/chat/v1/message/send-sync",
}


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class HelenaClient:
    """Cliente multi-tenant para Helena CRM API."""

    def __init__(
        self,
        api_token: str,
        base_url: str = "https://api.helena.run",
    ):
        """
        Args:
            api_token: Token de autenticacao do tenant.
            base_url: URL base da API Helena.
        """
        if not api_token:
            raise ValueError("api_token e obrigatorio para HelenaClient")

        self.api_token = api_token
        self.base_url = base_url.rstrip("/")

        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": self.api_token,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=HTTP_TIMEOUT,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Fecha o cliente HTTP."""
        await self.client.aclose()

    async def __aenter__(self) -> "HelenaClient":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Core -- Contacts
    # ------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(HTTP_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception(_is_retryable_http_error),
    )
    async def get_contact_by_phone(self, phone: str) -> Dict[str, Any]:
        """
        Busca contato por telefone, incluindo customFields.

        Helena GET nao retorna customFields; fazemos PUT com
        {"fields":["CustomFields"],"customFields":{}} para obte-los.
        """
        endpoint = HELENA_ENDPOINTS["get_contact_by_phone"].format(phone=phone)
        logger.debug("Helena GET contact %s", phone)

        response = await self.client.get(endpoint)
        response.raise_for_status()
        contact = response.json()

        # PUT trick to get custom fields
        try:
            update_ep = HELENA_ENDPOINTS["update_contact"].format(phone=phone)
            put_resp = await self.client.put(
                update_ep,
                json={"fields": ["CustomFields"], "customFields": {}},
            )
            put_resp.raise_for_status()
            put_data = put_resp.json()
            if put_data.get("customFields"):
                contact["customFields"] = put_data["customFields"]
        except Exception:
            logger.warning("Failed to fetch customFields for %s via PUT trick", phone)

        return contact

    @retry(
        stop=stop_after_attempt(HTTP_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception(_is_retryable_http_error),
    )
    async def update_contact(self, phone: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Atualiza dados do contato.

        Args:
            phone: Numero E.164.
            data: Dict com chaves opcionais: name, email, customFields.
        """
        endpoint = HELENA_ENDPOINTS["update_contact"].format(phone=phone)

        payload: Dict[str, Any] = {"fields": []}
        if "name" in data:
            payload["fields"].append("Name")
            payload["name"] = data["name"]
        if "email" in data:
            payload["fields"].append("Email")
            payload["email"] = data["email"]
        if "customFields" in data:
            payload["fields"].append("CustomFields")
            payload["customFields"] = data["customFields"]

        logger.debug("Helena PUT contact %s fields=%s", phone, payload["fields"])
        response = await self.client.put(endpoint, json=payload)
        response.raise_for_status()
        return response.json()

    @retry(
        stop=stop_after_attempt(HTTP_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception(_is_retryable_http_error),
    )
    async def add_contact_tags(self, phone: str, tags: List[str]) -> Dict[str, Any]:
        """Adiciona tags a um contato."""
        endpoint = HELENA_ENDPOINTS["add_contact_tags"].format(phone=phone)
        payload = {"tagNames": tags}

        logger.debug("Helena POST contact tags %s tags=%s", phone, tags)
        response = await self.client.post(endpoint, json=payload)
        response.raise_for_status()
        return response.json()

    @retry(
        stop=stop_after_attempt(HTTP_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception(_is_retryable_http_error),
    )
    async def get_contact_custom_fields(self) -> List[Dict[str, Any]]:
        """Retorna lista de definicoes de campos customizados de contato."""
        endpoint = HELENA_ENDPOINTS["get_contact_custom_fields"]
        logger.debug("Helena GET contact-custom-field")

        response = await self.client.get(endpoint)
        response.raise_for_status()
        return response.json()

    # ------------------------------------------------------------------
    # CRM -- Panels / Cards
    # ------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(HTTP_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception(_is_retryable_http_error),
    )
    async def get_panels(self) -> List[Dict[str, Any]]:
        """Retorna lista de paineis do CRM (extrai items da resposta paginada)."""
        endpoint = HELENA_ENDPOINTS["get_panels"]
        logger.debug("Helena GET panels")

        all_items: List[Dict[str, Any]] = []
        page = 1

        while True:
            response = await self.client.get(endpoint, params={"pageNumber": page, "pageSize": 50})
            response.raise_for_status()
            data = response.json()

            if isinstance(data, dict):
                items = data.get("items", [])
                all_items.extend(items)
                if not data.get("hasMorePages", False):
                    break
                page += 1
            else:
                all_items = data
                break

        return all_items

    @retry(
        stop=stop_after_attempt(HTTP_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception(_is_retryable_http_error),
    )
    async def get_panel_steps(self, panel_id: str) -> List[Dict[str, Any]]:
        """Retorna lista de steps de um painel buscando do endpoint individual."""
        endpoint = f"/crm/v1/panel/{panel_id}"
        logger.debug("Helena GET panel steps %s", panel_id)

        response = await self.client.get(endpoint)
        response.raise_for_status()
        data = response.json()

        steps = data.get("steps") or []
        return steps

    @retry(
        stop=stop_after_attempt(HTTP_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception(_is_retryable_http_error),
    )
    async def get_panel_custom_fields(self, panel_id: str) -> List[Dict[str, Any]]:
        """Retorna campos customizados de um painel."""
        endpoint = HELENA_ENDPOINTS["get_panel_custom_fields"].format(panel_id=panel_id)
        logger.debug("Helena GET panel custom fields %s", panel_id)

        response = await self.client.get(endpoint, params={"NestedList": "true"})
        response.raise_for_status()
        return response.json()

    @retry(
        stop=stop_after_attempt(HTTP_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception(_is_retryable_http_error),
    )
    async def duplicate_card(self, card_id: str, step_id: str) -> Dict[str, Any]:
        """Duplica card para outro step."""
        endpoint = HELENA_ENDPOINTS["duplicate_card"].format(card_id=card_id)

        payload = {
            "copyToStepId": step_id,
            "options": {
                "fields": ["All"],
                "archiveOriginalCard": True,
            },
        }

        logger.debug("Helena POST duplicate card %s -> step %s", card_id, step_id)
        response = await self.client.post(endpoint, json=payload)
        response.raise_for_status()
        return response.json()

    @retry(
        stop=stop_after_attempt(HTTP_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception(_is_retryable_http_error),
    )
    async def update_card(self, card_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Atualiza dados de um card.

        Args:
            card_id: UUID do card.
            data: Dict com chaves opcionais: title, description, contactIds,
                  dueDate (ISO string), tagNames, customFields.
        """
        endpoint = HELENA_ENDPOINTS["update_card"].format(card_id=card_id)

        payload: Dict[str, Any] = {"fields": []}

        field_map = {
            "title": "Title",
            "description": "Description",
            "contactIds": "ContactIds",
            "dueDate": "DueDate",
            "tagNames": "TagIds",
            "customFields": "CustomFields",
        }

        for key, helena_field in field_map.items():
            if key in data:
                payload["fields"].append(helena_field)
                payload[key] = data[key]

        logger.debug("Helena PUT card %s fields=%s", card_id, payload["fields"])
        response = await self.client.put(endpoint, json=payload)
        response.raise_for_status()
        return response.json()

    # ------------------------------------------------------------------
    # Chat -- Sessions / Messages
    # ------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(HTTP_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception(_is_retryable_http_error),
    )
    async def get_departments(self) -> List[Dict[str, Any]]:
        """Retorna lista de departamentos de chat."""
        endpoint = HELENA_ENDPOINTS["get_departments"]
        logger.debug("Helena GET departments")

        response = await self.client.get(endpoint)
        response.raise_for_status()
        return response.json()

    @retry(
        stop=stop_after_attempt(HTTP_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception(_is_retryable_http_error),
    )
    async def transfer_session(
        self, session_id: str, department_id: str
    ) -> Dict[str, Any]:
        """Transfere sessao de chat para outro departamento."""
        endpoint = HELENA_ENDPOINTS["transfer_session"].format(session_id=session_id)

        payload = {
            "type": "DEPARTMENT",
            "newDepartmentId": department_id,
        }

        logger.debug("Helena PUT transfer session %s -> dept %s", session_id, department_id)
        response = await self.client.put(endpoint, json=payload)
        response.raise_for_status()
        return response.json()

    @retry(
        stop=stop_after_attempt(HTTP_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception(_is_retryable_http_error),
    )
    async def complete_session(self, session_id: str) -> Dict[str, Any]:
        """Finaliza/completa uma sessao de chat."""
        endpoint = HELENA_ENDPOINTS["complete_session"].format(session_id=session_id)

        logger.debug("Helena PUT complete session %s", session_id)
        response = await self.client.put(endpoint)
        response.raise_for_status()
        return response.json()

    @retry(
        stop=stop_after_attempt(HTTP_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception(_is_retryable_http_error),
    )
    async def send_message(self, session_id: str, message: str, to: str = "") -> Dict[str, Any]:
        """
        Envia mensagem de texto numa sessao de chat.

        Args:
            session_id: UUID da sessao.
            message: Texto da mensagem.
            to: Numero do destinatario (obrigatorio pela API Helena).
        """
        endpoint = HELENA_ENDPOINTS["send_message"]

        payload = {
            "sessionId": session_id,
            "to": to,
            "body": {
                "text": message,
            },
        }

        logger.debug("Helena POST send_message session=%s len=%d", session_id, len(message))
        response = await self.client.post(endpoint, json=payload)
        response.raise_for_status()
        return response.json()

    async def send_message_fragmented(
        self, session_id: str, message: str, to: str = "", delay: float = 1.2
    ) -> List[Dict[str, Any]]:
        """
        Envia mensagem fragmentada em partes separadas para parecer mais natural.

        Regras:
        - Se a mensagem contém lista de confirmacao de dados (formato com *Campo:*),
          envia tudo junto numa mensagem so.
        - Caso contrario, divide por paragrafos (\n\n) e envia cada parte separada.
        - Paragrafos curtos consecutivos (< 80 chars) sao agrupados.
        """
        # Detectar se e confirmacao de dados (lista com *Campo:* ou negrito)
        is_confirmation = bool(re.search(
            r"\*[A-ZÀ-Ú][a-zà-ú]+.*:\*", message
        )) and message.count("*") >= 4

        if is_confirmation or len(message) <= 150:
            # Confirmacao ou mensagem curta -> envia tudo junto
            result = await self.send_message(session_id, message, to)
            return [result]

        # Dividir por paragrafos
        paragraphs = [p.strip() for p in message.split("\n\n") if p.strip()]

        if len(paragraphs) <= 1:
            # Sem paragrafos para dividir -> envia tudo junto
            result = await self.send_message(session_id, message, to)
            return [result]

        # Agrupar paragrafos curtos consecutivos
        fragments: list[str] = []
        current = ""
        for p in paragraphs:
            if current and len(current) + len(p) < 150:
                current = current + "\n\n" + p
            else:
                if current:
                    fragments.append(current)
                current = p
        if current:
            fragments.append(current)

        # Enviar cada fragmento com delay
        results = []
        for i, fragment in enumerate(fragments):
            result = await self.send_message(session_id, fragment, to)
            results.append(result)
            if i < len(fragments) - 1:
                await asyncio.sleep(delay)

        logger.info(
            "Fragmented message into %d parts for session %s",
            len(fragments), session_id
        )
        return results
