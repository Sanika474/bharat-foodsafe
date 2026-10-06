import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Sequence
from sqlalchemy import event, select, text
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.models.notifications_and_audit import AuditLog

GENESIS_PREVIOUS_HASH = "0" * 64


def get_lock_key(restaurant_id: uuid.UUID | str | None) -> int:
    """Generates a 64-bit signed integer advisory lock key for PostgreSQL pg_advisory_xact_lock."""
    scope_str = f"audit_chain_{str(restaurant_id) if restaurant_id else 'global'}"
    raw_int = int(hashlib.sha256(scope_str.encode("utf-8")).hexdigest()[:15], 16)
    if raw_int >= 2**63:
        raw_int -= 2**64
    return raw_int


def acquire_audit_chain_lock(db: Session, restaurant_id: uuid.UUID | str | None = None) -> None:
    """Acquires a PostgreSQL transaction-level advisory lock (pg_advisory_xact_lock)."""
    bind = db.get_bind()
    if bind and bind.dialect.name == "postgresql":
        lock_key = get_lock_key(restaurant_id)
        db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_key})


def format_datetime_canonical(dt: datetime) -> str:
    """Formats datetime object to a deterministic canonical ISO 8601 UTC string (%Y-%m-%dT%H:%M:%S.%fZ)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"


def compute_record_hash(
    restaurant_id: str | None,
    user_id: str | None,
    event_name: str,
    resource_type: str,
    resource_id: str | None,
    payload_jsonb: dict | list | None,
    previous_hash: str,
    created_at_iso: str,
) -> str:
    """
    Computes deterministic SHA-256 hash of canonicalized audit payload.
    """
    canonical_dict = {
        "created_at": created_at_iso,
        "event_name": event_name,
        "payload": payload_jsonb,
        "previous_hash": previous_hash,
        "resource_id": str(resource_id) if resource_id else None,
        "resource_type": resource_type,
        "restaurant_id": str(restaurant_id) if restaurant_id else None,
        "user_id": str(user_id) if user_id else None,
    }
    canonical_json = json.dumps(canonical_dict, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def record_audit_event(
    db: Session,
    event_name: str,
    resource_type: str,
    restaurant_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    resource_id: uuid.UUID | None = None,
    payload_jsonb: dict | list | None = None,
    created_at: datetime | None = None,
) -> AuditLog:
    """
    Appends a new cryptographically chained AuditLog record.
    Acquires advisory lock to prevent race conditions during concurrent inserts.
    """
    # 1. Acquire transaction-level advisory lock
    acquire_audit_chain_lock(db, restaurant_id)

    # 2. Get last audit record for scope
    stmt = select(AuditLog)
    if restaurant_id:
        stmt = stmt.where(AuditLog.restaurant_id == restaurant_id)
    else:
        stmt = stmt.where(AuditLog.restaurant_id.is_(None))
    stmt = stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(1)

    last_record = db.scalar(stmt)

    if last_record and last_record.record_hash:
        previous_hash = last_record.record_hash
    else:
        previous_hash = GENESIS_PREVIOUS_HASH

    # 3. Format created_at timestamp
    now = created_at or datetime.now(timezone.utc)
    created_at_iso = format_datetime_canonical(now)

    # 4. Calculate record_hash using canonical serialization
    r_id_str = str(restaurant_id) if restaurant_id else None
    u_id_str = str(user_id) if user_id else None
    res_id_str = str(resource_id) if resource_id else None

    rec_hash = compute_record_hash(
        restaurant_id=r_id_str,
        user_id=u_id_str,
        event_name=event_name,
        resource_type=resource_type,
        resource_id=res_id_str,
        payload_jsonb=payload_jsonb,
        previous_hash=previous_hash,
        created_at_iso=created_at_iso,
    )

    # 5. Create AuditLog instance
    audit_entry = AuditLog(
        id=uuid.uuid4(),
        restaurant_id=restaurant_id,
        user_id=user_id,
        event_name=event_name,
        resource_type=resource_type,
        resource_id=resource_id,
        payload_jsonb=payload_jsonb,
        previous_hash=previous_hash,
        record_hash=rec_hash,
        created_at=now,
    )

    db.add(audit_entry)
    db.flush()
    return audit_entry


def verify_audit_chain(
    db: Session,
    restaurant_id: uuid.UUID | str | None = None,
) -> dict:
    """
    Verifies the integrity of the audit hash chain.
    Detects:
    - Genesis previous_hash violation
    - Previous-hash linkage breaks / gaps
    - Payload/hash tampering (computed hash mismatch)
    """
    stmt = select(AuditLog)
    if restaurant_id:
        stmt = stmt.where(AuditLog.restaurant_id == restaurant_id)
    stmt = stmt.order_by(AuditLog.created_at.asc(), AuditLog.id.asc())

    records = db.scalars(stmt).all()

    errors = []
    expected_previous_hash = GENESIS_PREVIOUS_HASH

    for idx, record in enumerate(records):
        # 1. Check previous_hash linkage
        if record.previous_hash != expected_previous_hash:
            errors.append({
                "record_id": str(record.id),
                "index": idx,
                "error_type": "PREVIOUS_HASH_MISMATCH",
                "expected_previous_hash": expected_previous_hash,
                "found_previous_hash": record.previous_hash,
                "message": f"Linkage break at index {idx}: previous_hash '{record.previous_hash}' does not match expected '{expected_previous_hash}'."
            })

        # 2. Re-compute hash and check payload integrity
        created_at_iso = format_datetime_canonical(record.created_at) if record.created_at else ""
        expected_hash = compute_record_hash(
            restaurant_id=str(record.restaurant_id) if record.restaurant_id else None,
            user_id=str(record.user_id) if record.user_id else None,
            event_name=record.event_name,
            resource_type=record.resource_type,
            resource_id=str(record.resource_id) if record.resource_id else None,
            payload_jsonb=record.payload_jsonb,
            previous_hash=record.previous_hash,
            created_at_iso=created_at_iso,
        )

        if record.record_hash != expected_hash:
            errors.append({
                "record_id": str(record.id),
                "index": idx,
                "error_type": "TAMPERED_RECORD_HASH",
                "expected_record_hash": expected_hash,
                "found_record_hash": record.record_hash,
                "message": f"Tampering detected at index {idx}: computed hash '{expected_hash}' does not match stored '{record.record_hash}'."
            })

        # Set next record's expected previous_hash to current stored record_hash
        expected_previous_hash = record.record_hash

    is_valid = len(errors) == 0

    return {
        "is_valid": is_valid,
        "records_scanned": len(records),
        "errors": errors,
    }


def list_audit_logs(
    db: Session,
    restaurant_id: uuid.UUID | None = None,
    event_name: str | None = None,
    resource_type: str | None = None,
    resource_id: uuid.UUID | None = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[Sequence[AuditLog], int]:
    from sqlalchemy import and_, func
    stmt = select(AuditLog)
    count_stmt = select(func.count(AuditLog.id))

    filters = []
    if restaurant_id:
        filters.append(AuditLog.restaurant_id == restaurant_id)
    if event_name:
        filters.append(AuditLog.event_name == event_name)
    if resource_type:
        filters.append(AuditLog.resource_type == resource_type)
    if resource_id:
        filters.append(AuditLog.resource_id == resource_id)

    if filters:
        stmt = stmt.where(and_(*filters))
        count_stmt = count_stmt.where(and_(*filters))

    total = db.scalar(count_stmt) or 0
    stmt = stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).offset(skip).limit(limit)
    records = db.scalars(stmt).all()

    return records, total


def get_audit_log_by_id(db: Session, audit_id: uuid.UUID) -> AuditLog | None:
    stmt = select(AuditLog).where(AuditLog.id == audit_id)
    return db.scalar(stmt)


# Enforce Immutability via SQLAlchemy Events
@event.listens_for(AuditLog, "before_update")
def _prevent_audit_log_update(mapper, connection, target):
    raise AppException(
        code="AUDIT_LOG_IMMUTABLE",
        message="Audit log records are immutable and cannot be updated.",
        status_code=409,
    )


@event.listens_for(AuditLog, "before_delete")
def _prevent_audit_log_delete(mapper, connection, target):
    raise AppException(
        code="AUDIT_LOG_IMMUTABLE",
        message="Audit log records are immutable and cannot be deleted.",
        status_code=409,
    )
