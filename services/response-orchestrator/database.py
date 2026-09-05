"""
Database - Response Orchestrator Service
AI-Augmented SOC

SQLAlchemy async ORM models for defense plans, action executions,
and verification results. Shares the ai_soc PostgreSQL database.
"""

import logging
from typing import AsyncGenerator

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text, DateTime,
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


class DefensePlanModel(Base):
    """
    defense_plans table — one row per defense plan.
    """
    __tablename__ = "defense_plans"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    plan_id = Column(String(255), unique=True, nullable=False, index=True)
    incident_id = Column(String(255), nullable=False, index=True)
    simulation_id = Column(String(255), nullable=True)
    status = Column(String(30), default="triggered", nullable=False, index=True)

    # Context
    incident_summary = Column(Text, nullable=True)
    detected_techniques = Column(JSONB, default=list, nullable=False)
    kill_chain_stage = Column(String(50), nullable=True)
    source_ips = Column(JSONB, default=list, nullable=False)
    dest_ips = Column(JSONB, default=list, nullable=False)

    # Risk scores
    pre_defense_risk = Column(Float, nullable=True)
    post_defense_risk = Column(Float, nullable=True)
    simulation_summary = Column(JSONB, nullable=True)

    # Plan metadata
    rationale = Column(Text, nullable=True)
    total_actions = Column(Integer, default=0, nullable=False)
    auto_executed_count = Column(Integer, default=0, nullable=False)
    human_approved_count = Column(Integer, default=0, nullable=False)
    dry_run = Column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)


class PlannedActionModel(Base):
    """
    planned_actions table — one row per action within a defense plan.
    """
    __tablename__ = "planned_actions"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    plan_id = Column(
        String(255),
        ForeignKey("defense_plans.plan_id"),
        nullable=False,
        index=True
    )
    action_id = Column(String(255), unique=True, nullable=False, index=True)
    action_type = Column(String(50), nullable=False)
    target = Column(String(255), nullable=False)
    target_hostname = Column(String(255), nullable=True)
    adapter = Column(String(50), nullable=False)

    # Scoring
    confidence = Column(Float, nullable=False)
    impact_score = Column(Float, nullable=False)
    safety_score = Column(Float, nullable=False)
    composite_score = Column(Float, nullable=False)

    # Safety
    blast_radius = Column(String(20), nullable=False)
    approval_tier = Column(Integer, nullable=False)
    requires_approval = Column(Boolean, nullable=False)

    # MITRE mapping
    d3fend_technique = Column(String(100), nullable=True)
    d3fend_label = Column(String(255), nullable=True)
    counters_techniques = Column(JSONB, default=list, nullable=False)

    # Execution
    status = Column(String(30), default="pending", nullable=False, index=True)
    rationale = Column(Text, nullable=True)
    executed_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    rolled_back_at = Column(DateTime(timezone=True), nullable=True)
    adapter_response = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)

    # Approval
    approved_by = Column(String(255), nullable=True)
    approval_notes = Column(Text, nullable=True)


class VerificationResultModel(Base):
    """
    verification_results table — one row per verification run.
    """
    __tablename__ = "verification_results"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    plan_id = Column(
        String(255),
        ForeignKey("defense_plans.plan_id"),
        nullable=False,
        index=True
    )
    verified_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Re-simulation
    pre_attack_success_rate = Column(Float, nullable=False)
    post_attack_success_rate = Column(Float, nullable=False)
    risk_reduction_pct = Column(Float, nullable=False)
    re_simulation_id = Column(String(255), nullable=True)

    # Monitoring
    continued_indicators = Column(Boolean, default=False, nullable=False)
    monitoring_duration_seconds = Column(Integer, default=0, nullable=False)
    new_alerts_during_monitoring = Column(Integer, default=0, nullable=False)

    # Verdict
    verification_passed = Column(Boolean, nullable=False)
    verdict_reason = Column(Text, nullable=True)


class DefenseOutcomeModel(Base):
    """
    defense_outcomes table — feedback data for the learning loop.
    Records the relationship between actions taken and their measured impact.
    """
    __tablename__ = "defense_outcomes"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()")
    )
    plan_id = Column(String(255), nullable=False, index=True)
    action_type = Column(String(50), nullable=False, index=True)
    target = Column(String(255), nullable=False)
    countered_technique = Column(String(50), nullable=False, index=True)

    # Measured effectiveness
    pre_risk = Column(Float, nullable=False)
    post_risk = Column(Float, nullable=False)
    risk_delta = Column(Float, nullable=False)
    was_effective = Column(Boolean, nullable=False)

    recorded_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ---------------------------------------------------------------------------
# Engine management
# ---------------------------------------------------------------------------

_engine = None
_async_session_factory: async_sessionmaker = None


async def create_db_pool(database_url: str) -> None:
    """Create the async engine and session factory."""
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

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("database_pool_created")


async def close_db_pool() -> None:
    """Dispose the connection pool."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        logger.info("database_pool_closed")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an AsyncSession per request."""
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
    """Ping the database."""
    if _engine is None:
        return False
    try:
        async with _engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.warning("db_health_check_failed", extra={"error": str(e)})
        return False
