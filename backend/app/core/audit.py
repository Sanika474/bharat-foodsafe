import argparse
import hashlib
import json
import sys
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


def _verify_single_chain(
    db: Session,
    restaurant_id: uuid.UUID | str | None = None,
    is_global: bool = False,
) -> tuple[int, list[dict]]:
    """Helper that verifies an individual chain (for a tenant or global system scope)."""
    stmt = select(AuditLog)
    if is_global or restaurant_id is None:
        stmt = stmt.where(AuditLog.restaurant_id.is_(None))
    else:
        stmt = stmt.where(AuditLog.restaurant_id == restaurant_id)
    stmt = stmt.order_by(AuditLog.created_at.asc(), AuditLog.id.asc())

    records = db.scalars(stmt).all()
    errors = []
    expected_previous_hash = GENESIS_PREVIOUS_HASH

    for idx, record in enumerate(records):
        # 1. Check previous_hash linkage
        if record.previous_hash != expected_previous_hash:
            errors.append(
                {
                    "record_id": str(record.id),
                    "restaurant_id": str(record.restaurant_id) if record.restaurant_id else None,
                    "index": idx,
                    "error_type": "PREVIOUS_HASH_MISMATCH",
                    "expected_previous_hash": expected_previous_hash,
                    "found_previous_hash": record.previous_hash,
                    "message": f"Linkage break at index {idx}: previous_hash '{record.previous_hash}' does not match expected '{expected_previous_hash}'.",
                }
            )

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
            errors.append(
                {
                    "record_id": str(record.id),
                    "restaurant_id": str(record.restaurant_id) if record.restaurant_id else None,
                    "index": idx,
                    "error_type": "TAMPERED_RECORD_HASH",
                    "expected_record_hash": expected_hash,
                    "found_record_hash": record.record_hash,
                    "message": f"Tampering detected at index {idx}: computed hash '{expected_hash}' does not match stored '{record.record_hash}'.",
                }
            )

        # Set next record's expected previous_hash to current stored record_hash
        expected_previous_hash = record.record_hash

    return len(records), errors


def verify_audit_chain(
    db: Session,
    restaurant_id: uuid.UUID | str | None = None,
) -> dict:
    """
    Verifies the integrity of the audit hash chain.
    If restaurant_id is provided, verifies that tenant's chain.
    If restaurant_id is None, verifies all tenant chains and the global chain across the database.
    Detects:
    - Genesis previous_hash violation
    - Previous-hash linkage breaks / gaps
    - Payload/hash tampering (computed hash mismatch)
    """
    if restaurant_id is not None:
        records_scanned, errors = _verify_single_chain(db, restaurant_id=restaurant_id)
        return {
            "is_valid": len(errors) == 0,
            "records_scanned": records_scanned,
            "errors": errors,
        }

    # Verify all chains across all tenants and global scope
    total_scanned = 0
    all_errors = []

    tenant_ids = db.scalars(
        select(AuditLog.restaurant_id).where(AuditLog.restaurant_id.is_not(None)).distinct()
    ).all()

    for t_id in tenant_ids:
        scanned, errors = _verify_single_chain(db, restaurant_id=t_id)
        total_scanned += scanned
        all_errors.extend(errors)

    has_global = db.scalar(select(AuditLog.id).where(AuditLog.restaurant_id.is_(None)).limit(1))
    if has_global:
        scanned, errors = _verify_single_chain(db, restaurant_id=None, is_global=True)
        total_scanned += scanned
        all_errors.extend(errors)

    return {
        "is_valid": len(all_errors) == 0,
        "records_scanned": total_scanned,
        "errors": all_errors,
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


# ------------------------------------------------------------------------------
# Standalone CLI Verification Entrypoint
# ------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """
    CLI runner for Bharat FoodSafe audit-chain integrity verification.
    Usage:
        python -m app.core.audit [--restaurant-id <UUID>]
    Returns:
        0 - Valid chain (0 broken links)
        1 - Invalid chain (tampered or broken link detected)
        2 - Argument parsing or invalid UUID error
    """
    parser = argparse.ArgumentParser(
        description="Verify cryptographic hash chain integrity for Bharat FoodSafe audit logs."
    )
    parser.add_argument(
        "--restaurant-id",
        type=str,
        default=None,
        help="Optional UUID of a specific tenant to verify. If omitted, verifies all tenant and global chains.",
    )
    args = parser.parse_args(argv)

    target_id: uuid.UUID | None = None
    if args.restaurant_id:
        try:
            target_id = uuid.UUID(args.restaurant_id)
        except ValueError:
            print(
                f"Error: Invalid UUID for --restaurant-id: '{args.restaurant_id}'", file=sys.stderr
            )
            return 2

    # Lazy import to avoid circular dependency
    from app.core.database import SessionLocal

    with SessionLocal() as db:
        result = verify_audit_chain(db, restaurant_id=target_id)

    print("=" * 60)
    print("Bharat FoodSafe - Audit Chain Integrity Verification")
    print("=" * 60)
    scope_desc = f"Tenant {target_id}" if target_id else "All Tenant & Global Chains"
    print(f"Scope:           {scope_desc}")
    print(f"Records Scanned: {result['records_scanned']}")
    print(f"Status:          {'VALID' if result['is_valid'] else 'INVALID'}")
    print("-" * 60)

    if result["is_valid"]:
        print("PASS: Audit hash chain is intact with zero broken links or tampered records.")
        print("=" * 60)
        return 0
    else:
        print(f"FAIL: Detected {len(result['errors'])} integrity violation(s):")
        for err in result["errors"]:
            tenant_info = (
                f" [Tenant: {err.get('restaurant_id')}]" if err.get("restaurant_id") else ""
            )
            print(
                f"  - Record {err.get('record_id')}{tenant_info} at index {err.get('index')}: {err.get('error_type')}"
            )
            print(f"    {err.get('message')}")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
