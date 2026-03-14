"""
Database Connections (Multi-Tenant)
====================================
Manages connections to:
- Supabase (config tables: tenants, agents, panels, fields, etc.)
- PostgreSQL (dedicated: LangGraph checkpoints, memory)
Both as singletons.
"""

import logging
import ssl
from typing import Optional
from contextlib import asynccontextmanager

import asyncpg
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession
from sqlalchemy.orm import sessionmaker
from supabase import create_client, Client as SupabaseClient

from src.config.settings import settings

logger = logging.getLogger(__name__)


# =====================================================
# Supabase Client (config tables)
# =====================================================

_supabase_client: Optional[SupabaseClient] = None


def get_supabase_client() -> SupabaseClient:
    """
    Returns a singleton Supabase client for config tables
    (tenants, agents, panels, fields, admin_users, etc.).
    """
    global _supabase_client
    if _supabase_client is None:
        if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_KEY must be configured. "
                "These are required for multi-tenant config storage."
            )
        _supabase_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        logger.info(f"Supabase client initialized: {settings.SUPABASE_URL}")
    return _supabase_client


# =====================================================
# PostgreSQL Pool (dedicated DB for memory/checkpoints)
# =====================================================

class PostgresManager:
    """Manages asyncpg pool and SQLAlchemy engine for dedicated PostgreSQL."""

    def __init__(self):
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[sessionmaker] = None
        self._pool: Optional[asyncpg.Pool] = None

    async def initialize(self):
        """Initialize engine and connection pool."""
        if self._engine is None:
            self._engine = create_async_engine(
                settings.postgres_async_uri,
                pool_size=settings.DB_POOL_SIZE,
                max_overflow=settings.DB_MAX_OVERFLOW,
                pool_timeout=settings.DB_POOL_TIMEOUT,
                pool_recycle=settings.DB_POOL_RECYCLE,
                echo=False,
            )
            self._session_factory = sessionmaker(
                self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )

        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                host=settings.POSTGRES_HOST,
                port=settings.POSTGRES_PORT,
                database=settings.POSTGRES_DB,
                user=settings.POSTGRES_USER,
                password=settings.POSTGRES_PASSWORD,
                min_size=5,
                max_size=settings.DB_POOL_SIZE,
                timeout=settings.DB_POOL_TIMEOUT,
            )

        logger.info(
            f"PostgreSQL initialized: {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}"
            f"/{settings.POSTGRES_DB}"
        )

    async def close(self):
        """Close all connections."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None

        if self._pool:
            await self._pool.close()
            self._pool = None

        logger.info("PostgreSQL connections closed")

    @asynccontextmanager
    async def get_session(self):
        """Context manager for SQLAlchemy async session."""
        if not self._session_factory:
            await self.initialize()

        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    @asynccontextmanager
    async def get_connection(self):
        """Context manager for raw asyncpg connection."""
        if not self._pool:
            await self.initialize()

        async with self._pool.acquire() as connection:
            yield connection

    async def health_check(self) -> bool:
        """Check if PostgreSQL is accessible."""
        try:
            async with self.get_connection() as conn:
                result = await conn.fetchval("SELECT 1")
                return result == 1
        except Exception as e:
            logger.warning(f"PostgreSQL health check failed: {e}")
            return False


# Singleton
postgres_manager = PostgresManager()


# =====================================================
# Helper functions
# =====================================================

async def init_database():
    """Initialize database connections (call on app startup)."""
    await postgres_manager.initialize()
    # Set timezone
    async with postgres_manager.get_connection() as conn:
        await conn.execute(f"SET timezone = '{settings.TIMEZONE}'")
    logger.info("Database initialized")


async def close_database():
    """Close database connections (call on app shutdown)."""
    await postgres_manager.close()
    logger.info("Database connections closed")


async def get_postgres_pool() -> asyncpg.Pool:
    """Get the asyncpg pool (initialize if needed)."""
    if postgres_manager._pool is None:
        await postgres_manager.initialize()
    return postgres_manager._pool


# =====================================================
# Supabase RDG asyncpg Pool (direct SQL access)
# =====================================================

_supabase_pool: Optional[asyncpg.Pool] = None


async def get_supabase_pool() -> asyncpg.Pool:
    """Get asyncpg pool for direct SQL queries against Supabase RDG.

    Uses SUPABASE_DB_URL for connection. This is used by the auth system
    to query agentpolitico_admin_users and other config tables directly.
    """
    global _supabase_pool
    if _supabase_pool is None:
        if not settings.SUPABASE_DB_URL:
            raise ValueError(
                "SUPABASE_DB_URL must be configured for direct database access. "
                "Expected format: postgresql://postgres.PROJECT:[password]@host:port/postgres"
            )
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        _supabase_pool = await asyncpg.create_pool(
            dsn=settings.SUPABASE_DB_URL,
            min_size=2,
            max_size=10,
            timeout=30,
            ssl=ssl_ctx,
        )
        logger.info("Supabase RDG asyncpg pool initialized")
    return _supabase_pool


async def close_supabase_pool():
    """Close the Supabase RDG asyncpg pool."""
    global _supabase_pool
    if _supabase_pool is not None:
        await _supabase_pool.close()
        _supabase_pool = None
        logger.info("Supabase RDG asyncpg pool closed")
