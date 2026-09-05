"""
Database Models & Session Management - Feedback Service
AI-Augmented SOC

SQLAlchemy async models for alert persistence and analyst feedback.
Uses PostgreSQL with asyncpg driver.
"""

import logging
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, Text, DateTime, ForeignKey, Index,
    select, func, case, and_, desc
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, insert
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class AlertRecord(Base):
    """Every processed alert with its AI triage result."""
    __tablename__ = "alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_id = Column(String(255), unique=True, nullable=False, index=True)
    wazuh_alert_id = Column(String(255), nullable=True)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    source_ip = Column(String(45), nullable=True, index=True)
    dest_ip = Column(String(45), nullable=True, index=True)
    rule_id = Column(String(50), nullable=True)
    rule_description = Column(Text, nullable=True)
    rule_level = Column(Integer, nullable=True)
    raw_alert_json = Column(JSONB, nullable=True)
    triage_result_json = Column(JSONB, nullable=True)
    ai_severity = Column(String(20), nullable=True, index=True)
    ai_category = Column(String(50), nullable=True)
    ai_confidence = Column(Float, nullable=True)
    ai_is_true_positive = Column(Boolean, nullable=True)
    ml_prediction = Column(String(20), nullable=True)
    ml_confidence = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    feedback_count = Column(Integer, default=0)


class FeedbackRecord(Base):
    """Analyst corrections and feedback on triage results."""
    __tablename__ = "feedback"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_id = Column(
        String(255),
        ForeignKey("alerts.alert_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    analyst_id = Column(String(100), nullable=False, index=True)
    true_severity = Column(String(20), nullable=True)
    true_category = Column(String(50), nullable=True)
    is_false_positive = Column(Boolean, nullable=False, default=False)
    true_label = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class FeedbackReviewRecord(Base):
    """Independent review required before a feedback label enters retraining."""
    __tablename__ = "feedback_reviews"
    feedback_id = Column(UUID(as_uuid=True), ForeignKey("feedback.id", ondelete="CASCADE"), primary_key=True)
    reviewer_id = Column(String(100), nullable=False)
    approved = Column(Boolean, nullable=False)
    notes = Column(Text)
    reviewed_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


# Additional indexes
Index("idx_alerts_created", AlertRecord.created_at)
Index("idx_feedback_fp", FeedbackRecord.is_false_positive)


class DatabaseManager:
    """Manages async PostgreSQL connections and operations."""

    def __init__(self, database_url: str):
        self.engine = create_async_engine(
            database_url,
            echo=False,
            pool_size=10,
            max_overflow=5,
            pool_pre_ping=True,
        )
        self.session_factory = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def init_db(self):
        """Create tables if they don't exist."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables initialized")

    async def close(self):
        """Close the engine."""
        await self.engine.dispose()

    def session(self) -> AsyncSession:
        """Get a new async session."""
        return self.session_factory()

    # --- Alert Operations ---

    async def store_alert(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Persist an alert and its triage result. Upsert on alert_id."""
        values = {key: value for key, value in data.items() if value is not None}
        if "raw_alert" in values:
            values["raw_alert_json"] = values.pop("raw_alert")
        if "triage_result" in values:
            values["triage_result_json"] = values.pop("triage_result")
        async with self.session() as session:
            statement = insert(AlertRecord).values(**values)
            statement = statement.on_conflict_do_update(index_elements=["alert_id"], set_={
                key: getattr(statement.excluded, key) for key in values if key != "alert_id"
            })
            await session.execute(statement)
            await session.commit()
            return {"alert_id": data["alert_id"], "action": "upserted"}

    async def get_alert(self, alert_id: str) -> Optional[Dict[str, Any]]:
        """Get a single alert with its feedback."""
        async with self.session() as session:
            result = await session.execute(
                select(AlertRecord).where(AlertRecord.alert_id == alert_id)
            )
            record = result.scalar_one_or_none()
            if not record:
                return None

            # Get feedback for this alert
            fb_result = await session.execute(
                select(FeedbackRecord)
                .where(FeedbackRecord.alert_id == alert_id)
                .order_by(FeedbackRecord.created_at.desc())
            )
            feedback_records = fb_result.scalars().all()

            return {
                "alert_id": record.alert_id,
                "wazuh_alert_id": record.wazuh_alert_id,
                "timestamp": record.timestamp.isoformat() if record.timestamp else None,
                "source_ip": record.source_ip,
                "dest_ip": record.dest_ip,
                "rule_id": record.rule_id,
                "rule_description": record.rule_description,
                "rule_level": record.rule_level,
                "ai_severity": record.ai_severity,
                "ai_category": record.ai_category,
                "ai_confidence": record.ai_confidence,
                "ai_is_true_positive": record.ai_is_true_positive,
                "ml_prediction": record.ml_prediction,
                "ml_confidence": record.ml_confidence,
                "created_at": record.created_at.isoformat() if record.created_at else None,
                "feedback_count": record.feedback_count,
                "feedback": [
                    {
                        "feedback_id": str(fb.id),
                        "analyst_id": fb.analyst_id,
                        "true_severity": fb.true_severity,
                        "true_category": fb.true_category,
                        "is_false_positive": fb.is_false_positive,
                        "true_label": fb.true_label,
                        "notes": fb.notes,
                        "created_at": fb.created_at.isoformat() if fb.created_at else None,
                    }
                    for fb in feedback_records
                ],
            }

    async def query_alerts(
        self,
        limit: int = 50,
        offset: int = 0,
        severity: Optional[str] = None,
        source_ip: Optional[str] = None,
        dest_ip: Optional[str] = None,
        has_feedback: Optional[bool] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Query alerts with filtering and pagination."""
        async with self.session() as session:
            query = select(AlertRecord)
            count_query = select(func.count(AlertRecord.id))

            conditions = []
            if severity:
                conditions.append(AlertRecord.ai_severity == severity)
            if source_ip:
                conditions.append(AlertRecord.source_ip == source_ip)
            if dest_ip:
                conditions.append(AlertRecord.dest_ip == dest_ip)
            if has_feedback is True:
                conditions.append(AlertRecord.feedback_count > 0)
            elif has_feedback is False:
                conditions.append(AlertRecord.feedback_count == 0)
            if start_time:
                conditions.append(AlertRecord.created_at >= start_time)
            if end_time:
                conditions.append(AlertRecord.created_at <= end_time)

            if conditions:
                query = query.where(and_(*conditions))
                count_query = count_query.where(and_(*conditions))

            # Get total count
            total_result = await session.execute(count_query)
            total = total_result.scalar()

            # Get paginated results
            query = query.order_by(desc(AlertRecord.created_at)).limit(limit).offset(offset)
            result = await session.execute(query)
            records = result.scalars().all()

            return {
                "total": total,
                "limit": limit,
                "offset": offset,
                "alerts": [
                    {
                        "alert_id": r.alert_id,
                        "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                        "source_ip": r.source_ip,
                        "dest_ip": r.dest_ip,
                        "rule_description": r.rule_description,
                        "rule_level": r.rule_level,
                        "ai_severity": r.ai_severity,
                        "ai_category": r.ai_category,
                        "ai_confidence": r.ai_confidence,
                        "ml_prediction": r.ml_prediction,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                        "feedback_count": r.feedback_count,
                    }
                    for r in records
                ],
            }

    # --- Feedback Operations ---

    async def store_feedback(
        self, alert_id: str, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Store analyst feedback for an alert."""
        async with self.session() as session:
            # Verify alert exists
            result = await session.execute(
                select(AlertRecord).where(AlertRecord.alert_id == alert_id)
            )
            alert_record = result.scalar_one_or_none()
            if not alert_record:
                return None

            feedback = FeedbackRecord(
                alert_id=alert_id,
                analyst_id=data["analyst_id"],
                true_severity=data.get("true_severity"),
                true_category=data.get("true_category"),
                is_false_positive=data.get("is_false_positive", False),
                true_label=data.get("true_label"),
                notes=data.get("notes"),
            )
            session.add(feedback)

            # Increment feedback count on alert
            alert_record.feedback_count = (alert_record.feedback_count or 0) + 1
            await session.commit()

            return {
                "feedback_id": str(feedback.id),
                "alert_id": alert_id,
                "analyst_id": feedback.analyst_id,
                "is_false_positive": feedback.is_false_positive,
                "created_at": feedback.created_at.isoformat() if feedback.created_at else None,
            }

    async def review_feedback(self, feedback_id, reviewer_id, approved, notes=None):
        async with self.session() as session:
            feedback = await session.get(FeedbackRecord, uuid.UUID(feedback_id))
            if not feedback:
                return None
            if feedback.analyst_id == reviewer_id:
                raise ValueError("A different analyst must review the label")
            if approved and feedback.true_label not in {"BENIGN", "ATTACK"}:
                raise ValueError("Only validated binary labels are eligible for this model bundle")
            await session.merge(FeedbackReviewRecord(feedback_id=feedback.id, reviewer_id=reviewer_id,
                                approved=approved, notes=notes, reviewed_at=datetime.utcnow()))
            await session.commit()
            return {"feedback_id": feedback_id, "approved": approved, "reviewer_id": reviewer_id}

    async def get_feedback_stats(self) -> Dict[str, Any]:
        """Compute aggregated feedback statistics."""
        async with self.session() as session:
            # Total alerts
            total_alerts = (
                await session.execute(select(func.count(AlertRecord.id)))
            ).scalar()

            # Total feedback entries
            total_feedback = (
                await session.execute(select(func.count(FeedbackRecord.id)))
            ).scalar()

            # False positive count
            fp_count = (
                await session.execute(
                    select(func.count(FeedbackRecord.id)).where(
                        FeedbackRecord.is_false_positive.is_(True)
                    )
                )
            ).scalar()

            # Severity corrections
            sev_corrections = (
                await session.execute(
                    select(func.count(FeedbackRecord.id)).where(
                        FeedbackRecord.true_severity.isnot(None)
                    )
                )
            ).scalar()

            # Category corrections
            cat_corrections = (
                await session.execute(
                    select(func.count(FeedbackRecord.id)).where(
                        FeedbackRecord.true_category.isnot(None)
                    )
                )
            ).scalar()

            # Labeled for retraining
            labeled = (
                await session.execute(
                    select(func.count(FeedbackRecord.id)).where(
                        FeedbackRecord.true_label.isnot(None)
                    )
                )
            ).scalar()

            # Average confidence when analyst agrees (no false positive, no corrections)
            correct_conf = await session.execute(
                select(func.avg(AlertRecord.ai_confidence))
                .join(FeedbackRecord, FeedbackRecord.alert_id == AlertRecord.alert_id)
                .where(
                    FeedbackRecord.is_false_positive.is_(False),
                    FeedbackRecord.true_severity.is_(None),
                )
            )
            avg_conf_correct = correct_conf.scalar()

            # Average confidence when analyst disagrees
            wrong_conf = await session.execute(
                select(func.avg(AlertRecord.ai_confidence))
                .join(FeedbackRecord, FeedbackRecord.alert_id == AlertRecord.alert_id)
                .where(FeedbackRecord.is_false_positive.is_(True))
            )
            avg_conf_wrong = wrong_conf.scalar()

            # Top false positive source IPs
            top_fp_query = (
                select(
                    AlertRecord.source_ip,
                    func.count(FeedbackRecord.id).label("fp_count"),
                )
                .join(FeedbackRecord, FeedbackRecord.alert_id == AlertRecord.alert_id)
                .where(FeedbackRecord.is_false_positive.is_(True))
                .group_by(AlertRecord.source_ip)
                .order_by(desc("fp_count"))
                .limit(10)
            )
            top_fp_result = await session.execute(top_fp_query)
            top_fps = [
                {"source_ip": row[0] or "unknown", "false_positive_count": row[1]}
                for row in top_fp_result.all()
            ]

            fp_rate = (fp_count / total_feedback) if total_feedback > 0 else 0.0
            sev_rate = (sev_corrections / total_feedback) if total_feedback > 0 else 0.0

            return {
                "total_alerts": total_alerts or 0,
                "total_feedback": total_feedback or 0,
                "false_positive_count": fp_count or 0,
                "false_positive_rate": round(fp_rate, 4),
                "severity_corrections": sev_corrections or 0,
                "severity_correction_rate": round(sev_rate, 4),
                "category_corrections": cat_corrections or 0,
                "labeled_for_retraining": labeled or 0,
                "avg_confidence_when_correct": (
                    round(avg_conf_correct, 4) if avg_conf_correct else None
                ),
                "avg_confidence_when_wrong": (
                    round(avg_conf_wrong, 4) if avg_conf_wrong else None
                ),
                "top_false_positive_sources": top_fps,
            }

    async def check_health(self) -> bool:
        """Check database connectivity."""
        try:
            async with self.session() as session:
                await session.execute(select(func.now()))
                return True
        except Exception:
            return False
