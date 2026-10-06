import uuid
from datetime import datetime, timezone
from typing import Sequence
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, joinedload

from app.models.analytics_and_incidents import CorrectiveAction, Incident


def get_incident_by_id(db: Session, incident_id: uuid.UUID) -> Incident | None:
    stmt = (
        select(Incident)
        .options(joinedload(Incident.corrective_actions))
        .where(Incident.id == incident_id)
    )
    return db.scalar(stmt)


def get_incident_by_entry_id(db: Session, entry_id: uuid.UUID) -> Incident | None:
    stmt = (
        select(Incident)
        .options(joinedload(Incident.corrective_actions))
        .where(Incident.entry_id == entry_id)
    )
    return db.scalar(stmt)


def list_incidents(
    db: Session,
    restaurant_id: uuid.UUID | None = None,
    status: str | None = None,
    severity: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[Sequence[Incident], int]:
    stmt = select(Incident).options(joinedload(Incident.corrective_actions))
    count_stmt = select(func.count(Incident.id))

    filters = []
    if restaurant_id:
        filters.append(Incident.restaurant_id == restaurant_id)
    if status:
        filters.append(Incident.status == status)
    if severity:
        filters.append(Incident.severity == severity)

    if filters:
        stmt = stmt.where(and_(*filters))
        count_stmt = count_stmt.where(and_(*filters))

    total = db.scalar(count_stmt) or 0
    stmt = stmt.order_by(Incident.created_at.desc()).offset(skip).limit(limit)
    incidents = db.scalars(stmt).unique().all()

    return incidents, total


def create_incident(
    db: Session,
    restaurant_id: uuid.UUID,
    entry_id: uuid.UUID | None,
    title: str,
    description: str | None = None,
    severity: str = "CRITICAL",
    status: str = "OPEN",
    detected_by: uuid.UUID | None = None,
) -> Incident:
    incident = Incident(
        id=uuid.uuid4(),
        restaurant_id=restaurant_id,
        entry_id=entry_id,
        title=title,
        description=description,
        severity=severity,
        status=status,
        detected_by=detected_by,
    )
    db.add(incident)
    db.flush()
    return incident


def update_incident_status(
    db: Session,
    incident: Incident,
    status: str,
    resolved_at: datetime | None = None,
) -> Incident:
    incident.status = status
    if resolved_at is not None:
        incident.resolved_at = resolved_at
    db.flush()
    return incident


def get_corrective_action_by_id(db: Session, ca_id: uuid.UUID) -> CorrectiveAction | None:
    stmt = (
        select(CorrectiveAction)
        .options(joinedload(CorrectiveAction.incident))
        .where(CorrectiveAction.id == ca_id)
    )
    return db.scalar(stmt)


def list_corrective_actions(
    db: Session,
    restaurant_id: uuid.UUID | None = None,
    status: str | None = None,
    assigned_to: uuid.UUID | None = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[Sequence[CorrectiveAction], int]:
    stmt = select(CorrectiveAction).join(Incident, CorrectiveAction.incident_id == Incident.id).options(joinedload(CorrectiveAction.incident))
    count_stmt = select(func.count(CorrectiveAction.id)).join(Incident, CorrectiveAction.incident_id == Incident.id)

    filters = []
    if restaurant_id:
        filters.append(Incident.restaurant_id == restaurant_id)
    if status:
        filters.append(CorrectiveAction.status == status)
    if assigned_to:
        filters.append(CorrectiveAction.assigned_to == assigned_to)

    if filters:
        stmt = stmt.where(and_(*filters))
        count_stmt = count_stmt.where(and_(*filters))

    total = db.scalar(count_stmt) or 0
    stmt = stmt.order_by(CorrectiveAction.created_at.desc()).offset(skip).limit(limit)
    cas = db.scalars(stmt).unique().all()

    return cas, total


def create_corrective_action(
    db: Session,
    incident_id: uuid.UUID,
    action_text: str,
    assigned_to: uuid.UUID | None = None,
    status: str = "PENDING",
) -> CorrectiveAction:
    ca = CorrectiveAction(
        id=uuid.uuid4(),
        incident_id=incident_id,
        assigned_to=assigned_to,
        action_text=action_text,
        status=status,
    )
    db.add(ca)
    db.flush()
    return ca


def update_corrective_action(
    db: Session,
    ca: CorrectiveAction,
    status: str | None = None,
    assigned_to: uuid.UUID | None = None,
    recheck_entry_id: uuid.UUID | None = None,
    evidence_file_id: uuid.UUID | None = None,
    notes: str | None = None,
    verified_by: uuid.UUID | None = None,
    verified_at: datetime | None = None,
) -> CorrectiveAction:
    if status is not None:
        ca.status = status
    if assigned_to is not None:
        ca.assigned_to = assigned_to
    if recheck_entry_id is not None:
        ca.recheck_entry_id = recheck_entry_id
    if evidence_file_id is not None:
        ca.evidence_file_id = evidence_file_id
    if notes is not None:
        ca.notes = notes
    if verified_by is not None:
        ca.verified_by = verified_by
    if verified_at is not None:
        ca.verified_at = verified_at
    db.flush()
    return ca
