import uuid
from typing import Sequence
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, joinedload

from app.models.analytics_and_incidents import AnomalyResult
from app.models.identity import User
from app.models.tasks_and_rules import Entry, Task, TaskTemplate


def get_anomaly_result_by_id(db: Session, anomaly_id: uuid.UUID) -> AnomalyResult | None:
    stmt = (
        select(AnomalyResult)
        .options(
            joinedload(AnomalyResult.entry).joinedload(Entry.task).joinedload(Task.template),
            joinedload(AnomalyResult.entry).joinedload(Entry.user),
        )
        .where(AnomalyResult.id == anomaly_id)
    )
    return db.scalar(stmt)


def get_anomaly_result_by_entry_id(db: Session, entry_id: uuid.UUID) -> AnomalyResult | None:
    stmt = (
        select(AnomalyResult)
        .options(
            joinedload(AnomalyResult.entry).joinedload(Entry.task).joinedload(Task.template),
            joinedload(AnomalyResult.entry).joinedload(Entry.user),
        )
        .where(AnomalyResult.entry_id == entry_id)
    )
    return db.scalar(stmt)


def list_anomaly_results(
    db: Session,
    restaurant_id: uuid.UUID | None = None,
    decision: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[Sequence[AnomalyResult], int]:
    stmt = (
        select(AnomalyResult)
        .join(Entry, AnomalyResult.entry_id == Entry.id)
        .options(
            joinedload(AnomalyResult.entry).joinedload(Entry.task).joinedload(Task.template),
            joinedload(AnomalyResult.entry).joinedload(Entry.user),
        )
    )
    count_stmt = select(func.count(AnomalyResult.id)).join(Entry, AnomalyResult.entry_id == Entry.id)

    filters = []
    if restaurant_id:
        filters.append(Entry.restaurant_id == restaurant_id)
    if decision:
        filters.append(AnomalyResult.decision == decision)

    if filters:
        stmt = stmt.where(and_(*filters))
        count_stmt = count_stmt.where(and_(*filters))

    total = db.scalar(count_stmt) or 0
    stmt = stmt.order_by(AnomalyResult.created_at.desc()).offset(skip).limit(limit)
    results = db.scalars(stmt).unique().all()

    return results, total


def create_anomaly_result(
    db: Session,
    entry_id: uuid.UUID,
    decision: str,
    ml_score: float | None = None,
    baseline_score: float | None = None,
    reasons_jsonb: dict | None = None,
    model_version_id: uuid.UUID | None = None,
) -> AnomalyResult:
    result = AnomalyResult(
        id=uuid.uuid4(),
        entry_id=entry_id,
        model_version_id=model_version_id,
        baseline_score=baseline_score,
        ml_score=ml_score,
        decision=decision,
        reasons_jsonb=reasons_jsonb,
    )
    db.add(result)
    db.flush()
    return result
