"""
Database - Correlation Engine Service
AI-Augmented SOC

SQLAlchemy async ORM models and engine setup for incident and alert tables.
Shares the ai_soc PostgreSQL database with other services.
"""

import logging
from typing import AsyncGenerator

from sqlalchemy import (
    Column, String, Integer, Float, Text, DateTime,
    ForeignKey, func, text
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker
)
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class IncidentModel(Base):
    """
    incidents table - one row per correlated incident.
    """
    __tablename__ = "incidents"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    incident_id = Column(String(255), unique=True, nullable=False, index=True)
    status = Column(String(20), default="open", nullable=False, index=True)
    severity = Column(String(20), nullable=True)
    kill_chain_stage = Column(String(50), nullable=True)
    kill_chain_stages_seen = Column(JSONB, default=list, nullable=False)
    alert_count = Column(Integer, default=0, nullable=False)
    first_seen = Column(DateTime(timezone=True), nullable=True)
    last_seen = Column(DateTime(timezone=True), nullable=True, index=True)
    source_ips = Column(JSONB, default=list, nullable=False)
    dest_ips = Column(JSONB, default=list, nullable=False)
    mitre_techniques = Column(JSONB, default=list, nullable=False)
    mitre_tactics = Column(JSONB, default=list, nullable=False)
    summary = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    closed_at = Column(DateTime(timezone=True), nullable=True)


class IncidentAlertModel(Base):
    """
    incident_alerts table - one row per alert attached to an incident.
    """
    __tablename__ = "incident_alerts"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    incident_id = Column(
        String(255),
        ForeignKey("incidents.incident_id"),
        nullable=False,
        index=True
    )
    alert_id = Column(String(255), nullable=False)
    severity = Column(String(20), nullable=True)
    category = Column(String(50), nullable=True)
    kill_chain_stage = Column(String(50), nullable=True)
    added_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )


# Module-level engine and session factory — initialised in create_db_pool()
_engine = None
_async_session_factory: async_sessionmaker = None


async def create_db_pool(database_url: str) -> None:
    """
    Create the async engine and session factory.
    Called once during FastAPI lifespan startup.
    """
    global _engine, _async_session_factory

    _engine = create_async_engine(
        database_url,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        echo=False,
    )

    _async_session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Create tables if they don't already exist
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("database_pool_created")


async def close_db_pool() -> None:
    """Dispose the connection pool. Called on shutdown."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        logger.info("database_pool_closed")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an AsyncSession per request.
    """
    if _async_session_factory is None:
        raise RuntimeError("Database pool has not been initialised")
    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def check_db_health() -> bool:
    """
    Ping the database. Returns True if reachable, False otherwise.
    Used by the /health endpoint.
    """
    if _engine is None:
        return False
    try:
        async with _engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.warning("db_health_check_failed", extra={"error": str(e)})
        return False
