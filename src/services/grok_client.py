"""
Grok (xAI) LLM Client (Multi-Tenant)
======================================
Client for xAI Grok via LangChain.
Supports per-tenant API key and model configuration.
"""

import os
from typing import Optional
from langchain_openai import ChatOpenAI

from src.config.settings import settings


class GrokClient:
    """Client for Grok (xAI) LLM."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        base_url: Optional[str] = None,
    ):
        """
        Initialize Grok client.

        For multi-tenant: pass tenant-specific api_key and model.
        Falls back to global settings if not provided.
        """
        self.api_key = api_key or settings.GROK_API_KEY
        self.model = model or settings.GROK_MODEL
        self.temperature = temperature if temperature is not None else settings.GROK_TEMPERATURE
        self.top_p = top_p if top_p is not None else settings.GROK_TOP_P
        self.base_url = base_url or settings.GROK_BASE_URL

        if not self.api_key:
            raise ValueError("GROK_API_KEY not configured")

        self.llm = ChatOpenAI(
            model=self.model,
            api_key=self.api_key,
            base_url=self.base_url,
            temperature=self.temperature,
            top_p=self.top_p,
            streaming=False,
        )

    def get_llm(self) -> ChatOpenAI:
        """Return the configured LLM instance."""
        return self.llm


# Default singleton (uses global settings)
_default_client: Optional[GrokClient] = None


def get_grok_llm(
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    top_p: Optional[float] = None,
) -> ChatOpenAI:
    """
    Get a Grok LLM instance.

    If no custom params are provided, returns the default singleton.
    If custom params are provided, creates a new instance (for tenant-specific config).
    """
    global _default_client

    if any(p is not None for p in [api_key, model, temperature, top_p]):
        # Tenant-specific: create new instance
        client = GrokClient(
            api_key=api_key,
            model=model,
            temperature=temperature,
            top_p=top_p,
        )
        return client.get_llm()

    # Default singleton
    if _default_client is None:
        _default_client = GrokClient()
    return _default_client.get_llm()
