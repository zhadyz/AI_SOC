"""Transactional plan snapshots and append-only decision history.

One orchestrator process owns execution. PostgreSQL is the deployment backend;
SQLite is supported for isolated restart/persistence tests.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, JSON, String, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from services.response_orchestrator.models import DefensePlan


class Base(DeclarativeBase):
    pass


class PlanSnapshot(Base):
    __tablename__ = "response_plan_state"
    plan_id = Column(String(255), primary_key=True)
    document = Column(JSON, nullable=False)


class PlanEvent(Base):
    __tablename__ = "response_plan_events"
    event_id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    plan_id = Column(String(255), nullable=False, index=True)
    occurred_at = Column(DateTime(timezone=True), nullable=False)
    event = Column(String(80), nullable=False)
    detail = Column(JSON, nullable=False)


class PlanStore:
    def __init__(self, database_url):
        self.engine = create_async_engine(database_url, pool_pre_ping=True)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def initialize(self):
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def close(self):
        await self.engine.dispose()

    async def load(self):
        async with self.sessions() as session:
            records = (await session.execute(select(PlanSnapshot))).scalars().all()
            return [DefensePlan.model_validate(row.document) for row in records]

    async def save(self, plan, event, **detail):
        # Snapshot and audit event commit together. Failure propagates before
        # execution so actions cannot proceed without a durable intent record.
        async with self.sessions.begin() as session:
            await session.merge(PlanSnapshot(plan_id=plan.plan_id, document=plan.model_dump(mode="json")))
            session.add(PlanEvent(plan_id=plan.plan_id, event=event,
                                  occurred_at=datetime.now(timezone.utc), detail=detail))

    async def events(self, plan_id):
        async with self.sessions() as session:
            records = (await session.execute(select(PlanEvent).where(PlanEvent.plan_id == plan_id)
                                              .order_by(PlanEvent.occurred_at, PlanEvent.event_id))).scalars().all()
            return [{"event_id": row.event_id, "event": row.event, "occurred_at": row.occurred_at.isoformat(),
                     "detail": row.detail} for row in records]
