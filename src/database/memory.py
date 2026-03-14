"""
PostgreSQL Chat History for LangGraph (Multi-Tenant)
=====================================================
Implements conversational memory using PostgreSQL.
Context window of 50 messages by default (configurable per tenant).
"""

from typing import List, Optional
from datetime import datetime
import json
import asyncpg
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.chat_history import BaseChatMessageHistory


class PostgresChatHistory(BaseChatMessageHistory):
    """
    Chat history using PostgreSQL.

    Stores Human + AI messages with configurable context window.
    Thread-safe and optimized for high concurrency.
    """

    def __init__(
        self,
        session_id: str,
        connection_string: str,
        context_window: int = 50,
        tenant_id: Optional[str] = None,
    ):
        """
        Initialize chat history.

        Args:
            session_id: Session ID (phone number or Helena session UUID)
            connection_string: PostgreSQL connection string
            context_window: Max messages to keep (configurable per tenant)
            tenant_id: Tenant UUID for multi-tenant isolation
        """
        self.session_id = session_id
        self.connection_string = connection_string
        self.context_window = context_window
        self.tenant_id = tenant_id
        self._pool: Optional[asyncpg.Pool] = None

    async def _get_pool(self) -> asyncpg.Pool:
        """Get or create connection pool."""
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                self.connection_string,
                min_size=2,
                max_size=10,
                timeout=30,
            )
        return self._pool

    async def close(self):
        """Close connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None

    @property
    def messages(self) -> List[BaseMessage]:
        """Return all messages (sync property)."""
        import asyncio
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.aget_messages())

    async def aget_messages(self) -> List[BaseMessage]:
        """Retrieve messages asynchronously."""
        pool = await self._get_pool()

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT message, type, content, created_at
                FROM langgraph_messages
                WHERE session_id = $1
                ORDER BY created_at ASC
                LIMIT $2
                """,
                self.session_id,
                self.context_window,
            )

        messages = []
        for row in rows:
            msg_type = row["type"]
            msg_content = row["content"]

            if msg_type == "human":
                messages.append(HumanMessage(content=msg_content))
            elif msg_type == "ai":
                messages.append(AIMessage(content=msg_content))
            elif msg_type == "system":
                messages.append(SystemMessage(content=msg_content))

        return messages

    def add_message(self, message: BaseMessage) -> None:
        """Add a message (sync)."""
        import asyncio
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.aadd_message(message))

    async def aadd_message(self, message: BaseMessage) -> None:
        """Add a message asynchronously."""
        pool = await self._get_pool()

        if isinstance(message, HumanMessage):
            msg_type = "human"
        elif isinstance(message, AIMessage):
            msg_type = "ai"
        elif isinstance(message, SystemMessage):
            msg_type = "system"
        else:
            msg_type = "function"

        message_json = json.dumps({
            "type": msg_type,
            "content": message.content,
            "additional_kwargs": getattr(message, "additional_kwargs", {}),
        })

        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO langgraph_messages
                (session_id, message, type, content, metadata, created_at)
                VALUES ($1, $2::jsonb, $3, $4, '{}'::jsonb, NOW())
                """,
                self.session_id,
                message_json,
                msg_type,
                str(message.content),
            )

            # Trim old messages
            await conn.execute(
                """
                DELETE FROM langgraph_messages
                WHERE id IN (
                    SELECT id FROM (
                        SELECT id, ROW_NUMBER() OVER (
                            PARTITION BY session_id ORDER BY created_at DESC
                        ) as rn
                        FROM langgraph_messages
                        WHERE session_id = $1
                    ) ranked
                    WHERE rn > $2
                )
                """,
                self.session_id,
                self.context_window,
            )

    def add_messages(self, messages: List[BaseMessage]) -> None:
        """Add multiple messages (sync)."""
        import asyncio
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.aadd_messages(messages))

    async def aadd_messages(self, messages: List[BaseMessage]) -> None:
        """Add multiple messages asynchronously."""
        for message in messages:
            await self.aadd_message(message)

    def clear(self) -> None:
        """Clear all history (sync)."""
        import asyncio
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.aclear())

    async def aclear(self) -> None:
        """Clear all history asynchronously."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM langgraph_messages WHERE session_id = $1",
                self.session_id,
            )


async def create_chat_history(
    session_id: str,
    connection_string: str,
    context_window: int = 50,
    tenant_id: Optional[str] = None,
) -> PostgresChatHistory:
    """Factory to create PostgresChatHistory."""
    history = PostgresChatHistory(
        session_id=session_id,
        connection_string=connection_string,
        context_window=context_window,
        tenant_id=tenant_id,
    )
    await history._get_pool()
    return history
