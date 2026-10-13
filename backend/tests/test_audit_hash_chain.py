import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import (
    GENESIS_PREVIOUS_HASH,
    compute_record_hash,
    format_datetime_canonical,
    main as audit_cli_main,
    record_audit_event,
    verify_audit_chain,
)
from app.core.database import SessionLocal
from app.core.exceptions import AppException
from app.core.security import create_access_token
from app.main import app
from app.models.identity import Restaurant, Role, User, UserRole
from app.models.notifications_and_audit import AuditLog

client = TestClient(app)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def audit_test_data(db_session: Session):
    # Ensure roles
    staff_role = db_session.query(Role).filter_by(name="STAFF").first()
    if not staff_role:
        staff_role = Role(id=uuid.uuid4(), name="STAFF", is_system_role=True)
        db_session.add(staff_role)

    manager_role = db_session.query(Role).filter_by(name="MANAGER").first()
    if not manager_role:
        manager_role = Role(id=uuid.uuid4(), name="MANAGER", is_system_role=True)
        db_session.add(manager_role)

    db_session.commit()

    # Restaurants
    rest_a = Restaurant(
        id=uuid.uuid4(),
        name=f"Audit Test Rest A {uuid.uuid4().hex[:4]}",
        category="RESTAURANT",
        address_line1="100 Audit Way",
        city="Bengaluru",
        state="Karnataka",
        pincode="560001",
        status="ACTIVE",
    )
    rest_b = Restaurant(
        id=uuid.uuid4(),
        name=f"Audit Test Rest B {uuid.uuid4().hex[:4]}",
        category="CLOUD_KITCHEN",
        address_line1="200 Hash Rd",
        city="Mumbai",
        state="Maharashtra",
        pincode="400001",
        status="ACTIVE",
    )
    db_session.add_all([rest_a, rest_b])
    db_session.commit()

    # Users
    staff_a1 = User(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        name="Audit Staff A1",
        phone=f"+9171{uuid.uuid4().hex[:8]}",
        status="ACTIVE",
    )
    manager_a = User(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        name="Audit Manager A",
        phone=f"+9172{uuid.uuid4().hex[:8]}",
        status="ACTIVE",
    )
    staff_b1 = User(
        id=uuid.uuid4(),
        restaurant_id=rest_b.id,
        name="Audit Staff B1",
        phone=f"+9173{uuid.uuid4().hex[:8]}",
        status="ACTIVE",
    )
    manager_b = User(
        id=uuid.uuid4(),
        restaurant_id=rest_b.id,
        name="Audit Manager B",
        phone=f"+9174{uuid.uuid4().hex[:8]}",
        status="ACTIVE",
    )
    db_session.add_all([staff_a1, manager_a, staff_b1, manager_b])
    db_session.commit()

    db_session.add(
        UserRole(
            id=uuid.uuid4(), user_id=staff_a1.id, role_id=staff_role.id, restaurant_id=rest_a.id
        )
    )
    db_session.add(
        UserRole(
            id=uuid.uuid4(), user_id=manager_a.id, role_id=manager_role.id, restaurant_id=rest_a.id
        )
    )
    db_session.add(
        UserRole(
            id=uuid.uuid4(), user_id=staff_b1.id, role_id=staff_role.id, restaurant_id=rest_b.id
        )
    )
    db_session.add(
        UserRole(
            id=uuid.uuid4(), user_id=manager_b.id, role_id=manager_role.id, restaurant_id=rest_b.id
        )
    )
    db_session.commit()

    token_staff_a1, _ = create_access_token(
        user_id=staff_a1.id, tenant_id=rest_a.id, roles=["STAFF"]
    )
    token_manager_a, _ = create_access_token(
        user_id=manager_a.id, tenant_id=rest_a.id, roles=["MANAGER"]
    )
    token_staff_b1, _ = create_access_token(
        user_id=staff_b1.id, tenant_id=rest_b.id, roles=["STAFF"]
    )
    token_manager_b, _ = create_access_token(
        user_id=manager_b.id, tenant_id=rest_b.id, roles=["MANAGER"]
    )

    yield {
        "rest_a": rest_a,
        "rest_b": rest_b,
        "staff_a1": staff_a1,
        "manager_a": manager_a,
        "staff_b1": staff_b1,
        "manager_b": manager_b,
        "token_staff_a1": token_staff_a1,
        "token_manager_a": token_manager_a,
        "token_staff_b1": token_staff_b1,
        "token_manager_b": token_manager_b,
    }

    # Cleanup
    db_session.query(AuditLog).delete()
    db_session.query(UserRole).delete()
    db_session.query(User).delete()
    db_session.query(Restaurant).delete()
    db_session.commit()


# ------------------------------------------------------------------------------
# 1. Genesis / First Record & Hash Chaining
# ------------------------------------------------------------------------------


def test_first_genesis_audit_record(audit_test_data, db_session: Session):
    rest_id = audit_test_data["rest_a"].id
    user_id = audit_test_data["staff_a1"].id

    rec1 = record_audit_event(
        db=db_session,
        event_name="TEST_GENESIS_EVENT",
        resource_type="test_resource",
        restaurant_id=rest_id,
        user_id=user_id,
        payload_jsonb={"foo": "bar"},
    )
    db_session.commit()

    assert rec1.previous_hash == GENESIS_PREVIOUS_HASH
    assert len(rec1.record_hash) == 64

    # Verify chain
    res = verify_audit_chain(db_session, restaurant_id=rest_id)
    assert res["is_valid"] is True
    assert res["records_scanned"] == 1


def test_sequential_hash_chaining(audit_test_data, db_session: Session):
    rest_id = audit_test_data["rest_a"].id
    user_id = audit_test_data["staff_a1"].id

    # Create 5 sequential audit events
    rec1 = record_audit_event(
        db=db_session,
        event_name="EVENT_1",
        resource_type="type1",
        restaurant_id=rest_id,
        user_id=user_id,
    )
    rec2 = record_audit_event(
        db=db_session,
        event_name="EVENT_2",
        resource_type="type2",
        restaurant_id=rest_id,
        user_id=user_id,
    )
    rec3 = record_audit_event(
        db=db_session,
        event_name="EVENT_3",
        resource_type="type3",
        restaurant_id=rest_id,
        user_id=user_id,
    )
    rec4 = record_audit_event(
        db=db_session,
        event_name="EVENT_4",
        resource_type="type4",
        restaurant_id=rest_id,
        user_id=user_id,
    )
    rec5 = record_audit_event(
        db=db_session,
        event_name="EVENT_5",
        resource_type="type5",
        restaurant_id=rest_id,
        user_id=user_id,
    )
    db_session.commit()

    assert rec1.previous_hash == GENESIS_PREVIOUS_HASH
    assert rec2.previous_hash == rec1.record_hash
    assert rec3.previous_hash == rec2.record_hash
    assert rec4.previous_hash == rec3.record_hash
    assert rec5.previous_hash == rec4.record_hash

    # Verify audit chain integrity
    res = verify_audit_chain(db_session, restaurant_id=rest_id)
    assert res["is_valid"] is True
    assert res["records_scanned"] == 5
    assert len(res["errors"]) == 0


# ------------------------------------------------------------------------------
# 2. Deterministic Canonical Serialization
# ------------------------------------------------------------------------------


def test_deterministic_canonical_hash():
    now_iso = datetime.now(timezone.utc).isoformat()
    h1 = compute_record_hash(
        restaurant_id="123e4567-e89b-12d3-a456-426614174000",
        user_id="123e4567-e89b-12d3-a456-426614174001",
        event_name="USER_LOGIN",
        resource_type="user",
        resource_id="123e4567-e89b-12d3-a456-426614174001",
        payload_jsonb={"b": 2, "a": 1},  # Unsorted keys
        previous_hash="0" * 64,
        created_at_iso=now_iso,
    )

    h2 = compute_record_hash(
        restaurant_id="123e4567-e89b-12d3-a456-426614174000",
        user_id="123e4567-e89b-12d3-a456-426614174001",
        event_name="USER_LOGIN",
        resource_type="user",
        resource_id="123e4567-e89b-12d3-a456-426614174001",
        payload_jsonb={"a": 1, "b": 2},  # Re-ordered keys
        previous_hash="0" * 64,
        created_at_iso=now_iso,
    )

    assert h1 == h2


# ------------------------------------------------------------------------------
# 3. Tenant Isolation
# ------------------------------------------------------------------------------


def test_tenant_isolated_audit_chains(audit_test_data, db_session: Session):
    rest_a_id = audit_test_data["rest_a"].id
    rest_b_id = audit_test_data["rest_b"].id

    rec_a1 = record_audit_event(
        db=db_session, event_name="EVENT_A1", resource_type="entry", restaurant_id=rest_a_id
    )
    rec_b1 = record_audit_event(
        db=db_session, event_name="EVENT_B1", resource_type="entry", restaurant_id=rest_b_id
    )
    rec_a2 = record_audit_event(
        db=db_session, event_name="EVENT_A2", resource_type="entry", restaurant_id=rest_a_id
    )
    db_session.commit()

    # Rest A genesis
    assert rec_a1.previous_hash == GENESIS_PREVIOUS_HASH

    # Rest B genesis (independent chain!)
    assert rec_b1.previous_hash == GENESIS_PREVIOUS_HASH

    # Rest A second record links to Rest A first record
    assert rec_a2.previous_hash == rec_a1.record_hash

    res_a = verify_audit_chain(db_session, restaurant_id=rest_a_id)
    assert res_a["is_valid"] is True
    assert res_a["records_scanned"] == 2

    res_b = verify_audit_chain(db_session, restaurant_id=rest_b_id)
    assert res_b["is_valid"] is True
    assert res_b["records_scanned"] == 1


def test_cross_tenant_audit_log_by_id_forbidden(audit_test_data, db_session: Session):
    rest_a_id = audit_test_data["rest_a"].id
    rec_a = record_audit_event(
        db=db_session,
        event_name="CONFIDENTIAL_A_EVENT",
        resource_type="entry",
        restaurant_id=rest_a_id,
    )
    db_session.commit()

    # Manager B attempts to retrieve Tenant A's audit record by ID -> 403 FORBIDDEN_CROSS_TENANT
    res = client.get(
        f"/api/v1/audit/logs/{rec_a.id}",
        headers={"Authorization": f"Bearer {audit_test_data['token_manager_b']}"},
    )
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "FORBIDDEN_CROSS_TENANT"

    # Staff B also rejected by role guard -> 403
    res_staff = client.get(
        f"/api/v1/audit/logs/{rec_a.id}",
        headers={"Authorization": f"Bearer {audit_test_data['token_staff_b1']}"},
    )
    assert res_staff.status_code == 403


def test_cross_tenant_audit_logs_list_isolated(audit_test_data, db_session: Session):
    rest_a_id = audit_test_data["rest_a"].id
    rest_b_id = audit_test_data["rest_b"].id

    rec_a = record_audit_event(
        db=db_session, event_name="REST_A_EVENT", resource_type="entry", restaurant_id=rest_a_id
    )
    rec_b = record_audit_event(
        db=db_session, event_name="REST_B_EVENT", resource_type="entry", restaurant_id=rest_b_id
    )
    db_session.commit()

    # Manager B lists audit logs
    res = client.get(
        "/api/v1/audit/logs",
        headers={"Authorization": f"Bearer {audit_test_data['token_manager_b']}"},
    )
    assert res.status_code == 200
    data = res.json()["data"]
    log_ids = [log_item["id"] for log_item in data["logs"]]

    # Assert Tenant B's log is present, Tenant A's log is completely excluded
    assert str(rec_b.id) in log_ids
    assert str(rec_a.id) not in log_ids
    for log_item in data["logs"]:
        assert log_item["restaurant_id"] == str(rest_b_id)


def test_cross_tenant_audit_chain_verification_isolated(audit_test_data, db_session: Session):
    rest_a_id = audit_test_data["rest_a"].id
    rest_b_id = audit_test_data["rest_b"].id

    rec_a1 = record_audit_event(
        db=db_session, event_name="REST_A_1", resource_type="entry", restaurant_id=rest_a_id
    )
    record_audit_event(
        db=db_session, event_name="REST_A_2", resource_type="entry", restaurant_id=rest_a_id
    )
    record_audit_event(
        db=db_session, event_name="REST_B_1", resource_type="entry", restaurant_id=rest_b_id
    )
    db_session.commit()

    # Tamper with Tenant A's record hash to simulate a broken chain in Tenant A
    db_session.query(AuditLog).filter_by(id=rec_a1.id).update({"record_hash": "0" * 64})
    db_session.commit()

    # Manager B triggers audit verification via API:
    # Must remain valid and scan strictly Tenant B's 1 record (not affected by Tenant A's corrupted chain)
    res_b = client.post(
        "/api/v1/audit/verify",
        headers={"Authorization": f"Bearer {audit_test_data['token_manager_b']}"},
    )
    assert res_b.status_code == 200
    data_b = res_b.json()["data"]
    assert data_b["is_valid"] is True
    assert data_b["records_scanned"] == 1

    # Contrast with Manager A: Tenant A's broken chain is detected
    res_a = client.post(
        "/api/v1/audit/verify",
        headers={"Authorization": f"Bearer {audit_test_data['token_manager_a']}"},
    )
    assert res_a.status_code == 200
    data_a = res_a.json()["data"]
    assert data_a["is_valid"] is False


# ------------------------------------------------------------------------------
# 4. Immutability & Transaction Rollback
# ------------------------------------------------------------------------------


def test_audit_log_immutability_update_blocked(audit_test_data, db_session: Session):
    rec = record_audit_event(
        db=db_session,
        event_name="EVENT_ORIGINAL",
        resource_type="entry",
        restaurant_id=audit_test_data["rest_a"].id,
    )
    db_session.commit()

    rec.event_name = "EVENT_TAMPERED"
    with pytest.raises(AppException) as exc_info:
        db_session.commit()

    assert exc_info.value.code == "AUDIT_LOG_IMMUTABLE"
    db_session.rollback()


def test_transaction_rollback_prevents_orphaned_audit(audit_test_data, db_session: Session):
    rest_id = audit_test_data["rest_a"].id

    try:
        # Start transaction
        record_audit_event(
            db=db_session,
            event_name="EVENT_TRANSIENT",
            resource_type="entry",
            restaurant_id=rest_id,
        )
        # Simulate business failure
        raise ValueError("Business transaction failed")
    except ValueError:
        db_session.rollback()

    # Verify no audit entry exists
    res = verify_audit_chain(db_session, restaurant_id=rest_id)
    assert res["records_scanned"] == 0


# ------------------------------------------------------------------------------
# 5. Tampering & Gap Detection Tests
# ------------------------------------------------------------------------------


def test_tampered_payload_detection(audit_test_data, db_session: Session):
    rest_id = audit_test_data["rest_a"].id

    record_audit_event(
        db=db_session,
        event_name="EVENT_1",
        resource_type="entry",
        restaurant_id=rest_id,
        payload_jsonb={"temp": 3.5},
    )
    rec2 = record_audit_event(
        db=db_session,
        event_name="EVENT_2",
        resource_type="entry",
        restaurant_id=rest_id,
        payload_jsonb={"temp": 4.0},
    )
    db_session.commit()

    # Directly mutate database payload behind the scenes
    db_session.execute(
        AuditLog.__table__.update()
        .where(AuditLog.id == rec2.id)
        .values(payload_jsonb={"temp": 99.9})
    )
    db_session.commit()
    db_session.expire_all()

    res = verify_audit_chain(db_session, restaurant_id=rest_id)
    assert res["is_valid"] is False
    assert len(res["errors"]) > 0
    assert any(e["error_type"] == "TAMPERED_RECORD_HASH" for e in res["errors"])


def test_tampered_hash_and_broken_link_detection(audit_test_data, db_session: Session):
    rest_id = audit_test_data["rest_a"].id

    record_audit_event(
        db=db_session, event_name="EVENT_1", resource_type="entry", restaurant_id=rest_id
    )
    rec2 = record_audit_event(
        db=db_session, event_name="EVENT_2", resource_type="entry", restaurant_id=rest_id
    )
    record_audit_event(
        db=db_session, event_name="EVENT_3", resource_type="entry", restaurant_id=rest_id
    )
    db_session.commit()

    # Tamper record_hash of rec2 directly in DB
    fake_hash = "f" * 64
    db_session.execute(
        AuditLog.__table__.update().where(AuditLog.id == rec2.id).values(record_hash=fake_hash)
    )
    db_session.commit()
    db_session.expire_all()

    res = verify_audit_chain(db_session, restaurant_id=rest_id)
    assert res["is_valid"] is False
    # Should detect both TAMPERED_RECORD_HASH on rec2 and PREVIOUS_HASH_MISMATCH on rec3!
    error_types = [e["error_type"] for e in res["errors"]]
    assert "TAMPERED_RECORD_HASH" in error_types
    assert "PREVIOUS_HASH_MISMATCH" in error_types


# ------------------------------------------------------------------------------
# 6. API Authorization & Endpoints
# ------------------------------------------------------------------------------


def test_api_list_audit_logs_manager_allowed(audit_test_data, db_session: Session):
    rest_id = audit_test_data["rest_a"].id
    record_audit_event(
        db=db_session, event_name="EVENT_API_TEST", resource_type="entry", restaurant_id=rest_id
    )
    db_session.commit()

    token_mgr = audit_test_data["token_manager_a"]
    res = client.get(
        "/api/v1/audit/logs",
        headers={"Authorization": f"Bearer {token_mgr}"},
    )
    assert res.status_code == 200
    assert res.json()["success"] is True
    assert res.json()["data"]["total"] >= 1


def test_api_list_audit_logs_staff_denied(audit_test_data):
    token_staff = audit_test_data["token_staff_a1"]
    res = client.get(
        "/api/v1/audit/logs",
        headers={"Authorization": f"Bearer {token_staff}"},
    )
    assert res.status_code == 403


def test_api_verify_audit_chain_endpoint(audit_test_data, db_session: Session):
    rest_id = audit_test_data["rest_a"].id
    record_audit_event(
        db=db_session, event_name="EVENT_API_VERIFY", resource_type="entry", restaurant_id=rest_id
    )
    db_session.commit()

    token_mgr = audit_test_data["token_manager_a"]
    res = client.post(
        "/api/v1/audit/verify",
        headers={"Authorization": f"Bearer {token_mgr}"},
    )
    assert res.status_code == 200
    assert res.json()["success"] is True
    assert res.json()["data"]["is_valid"] is True
    assert res.json()["data"]["records_scanned"] >= 1


def test_api_audit_mutation_prohibited(audit_test_data, db_session: Session):
    rec = record_audit_event(
        db=db_session,
        event_name="EVENT_IMMUTABLE",
        resource_type="entry",
        restaurant_id=audit_test_data["rest_a"].id,
    )
    db_session.commit()

    token_mgr = audit_test_data["token_manager_a"]
    res = client.delete(
        f"/api/v1/audit/logs/{rec.id}",
        headers={"Authorization": f"Bearer {token_mgr}"},
    )
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "AUDIT_LOG_IMMUTABLE"


# ------------------------------------------------------------------------------
# 5. Concurrency & CLI Verification Tests (Phase 6, Task 6.1.4)
# ------------------------------------------------------------------------------


def test_concurrent_audit_writes_maintain_chain_integrity(audit_test_data, db_session: Session):
    """
    Verifies that multiple concurrent writers appending to the same tenant's audit chain
    using PostgreSQL transaction advisory locks (pg_advisory_xact_lock) maintain complete
    hash-chain integrity without dropped records or broken links.
    """
    rest_a_id = audit_test_data["rest_a"].id
    staff_a1 = audit_test_data["staff_a1"]
    num_writers = 8
    writes_per_writer = 3
    total_records = num_writers * writes_per_writer

    def worker_write(writer_id: int, seq: int) -> str:
        with SessionLocal() as session:
            rec = record_audit_event(
                db=session,
                event_name=f"CONCURRENT_OP_W{writer_id}_S{seq}",
                resource_type="entry",
                restaurant_id=rest_a_id,
                user_id=staff_a1.id,
                payload_jsonb={
                    "writer_id": writer_id,
                    "seq": seq,
                    "data": f"payload_{writer_id}_{seq}",
                },
            )
            session.commit()
            return str(rec.id)

    with ThreadPoolExecutor(max_workers=num_writers) as executor:
        futures = [
            executor.submit(worker_write, w, s)
            for w in range(num_writers)
            for s in range(writes_per_writer)
        ]
        created_ids = [f.result() for f in as_completed(futures)]

    # 1. Assert all intended records are persisted with unique IDs
    assert len(created_ids) == total_records
    assert len(set(created_ids)) == total_records

    # 2. Assert verify_audit_chain confirms zero broken links
    res = verify_audit_chain(db_session, restaurant_id=rest_a_id)
    assert res["is_valid"] is True
    assert res["records_scanned"] == total_records
    assert len(res["errors"]) == 0

    # 3. Explicit inspection of canonical chain linkage and stored hashes
    records = (
        db_session.query(AuditLog)
        .filter_by(restaurant_id=rest_a_id)
        .order_by(AuditLog.created_at.asc(), AuditLog.id.asc())
        .all()
    )
    assert len(records) == total_records

    for idx, rec in enumerate(records):
        # Genesis link
        if idx == 0:
            assert rec.previous_hash == GENESIS_PREVIOUS_HASH
        else:
            assert rec.previous_hash == records[idx - 1].record_hash

        # Canonical hash re-computation matches stored record_hash
        created_at_iso = format_datetime_canonical(rec.created_at)
        expected_hash = compute_record_hash(
            restaurant_id=str(rec.restaurant_id),
            user_id=str(rec.user_id),
            event_name=rec.event_name,
            resource_type=rec.resource_type,
            resource_id=str(rec.resource_id) if rec.resource_id else None,
            payload_jsonb=rec.payload_jsonb,
            previous_hash=rec.previous_hash,
            created_at_iso=created_at_iso,
        )
        assert rec.record_hash == expected_hash


def test_cross_tenant_concurrent_writes_parallel_and_isolated(audit_test_data, db_session: Session):
    """
    Verifies that concurrent writes targeting different tenants execute in parallel
    using independent per-tenant advisory lock keys without cross-tenant interference.
    """
    rest_a_id = audit_test_data["rest_a"].id
    rest_b_id = audit_test_data["rest_b"].id
    total_per_tenant = 6

    def write_event(target_rest_id: uuid.UUID, seq: int) -> str:
        with SessionLocal() as session:
            rec = record_audit_event(
                db=session,
                event_name=f"PARALLEL_REST_{seq}",
                resource_type="entry",
                restaurant_id=target_rest_id,
                payload_jsonb={"seq": seq},
            )
            session.commit()
            return str(rec.id)

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures_a = [executor.submit(write_event, rest_a_id, i) for i in range(total_per_tenant)]
        futures_b = [executor.submit(write_event, rest_b_id, i) for i in range(total_per_tenant)]
        for f in as_completed(futures_a + futures_b):
            f.result()

    # Verify Tenant A chain
    res_a = verify_audit_chain(db_session, restaurant_id=rest_a_id)
    assert res_a["is_valid"] is True
    assert res_a["records_scanned"] == total_per_tenant

    # Verify Tenant B chain
    res_b = verify_audit_chain(db_session, restaurant_id=rest_b_id)
    assert res_b["is_valid"] is True
    assert res_b["records_scanned"] == total_per_tenant

    # Verify system-wide multi-tenant aggregation
    res_all = verify_audit_chain(db_session, restaurant_id=None)
    assert res_all["is_valid"] is True
    assert res_all["records_scanned"] == total_per_tenant * 2


def test_unprotected_concurrent_writes_detects_broken_chain(audit_test_data, db_session: Session):
    """
    Proves that without concurrency locking, concurrent writers reading the same
    previous record simultaneously produce an invalid forked chain with duplicate
    previous_hash values, and verify_audit_chain reliably detects this integrity violation.
    """
    rest_a_id = audit_test_data["rest_a"].id
    barrier = threading.Barrier(2)

    # 1. Seed a genesis record for rest_a
    record_audit_event(
        db=db_session,
        event_name="GENESIS_RECORD",
        resource_type="entry",
        restaurant_id=rest_a_id,
    )
    db_session.commit()

    # 2. Two unprotected writers that deliberately race by querying last_record simultaneously
    def unprotected_race_writer(thread_id: int):
        with SessionLocal() as session:
            # Step A: Query last record without acquiring advisory lock
            stmt = (
                select(AuditLog)
                .where(AuditLog.restaurant_id == rest_a_id)
                .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
                .limit(1)
            )
            last_record = session.scalar(stmt)
            prev_hash = last_record.record_hash

            # Step B: Wait for both threads to have read the same previous record
            barrier.wait()

            # Step C: Both compute record_hash using the same previous_hash
            now = datetime.now(timezone.utc)
            now_iso = format_datetime_canonical(now)
            rec_hash = compute_record_hash(
                restaurant_id=str(rest_a_id),
                user_id=None,
                event_name=f"RACE_WRITE_{thread_id}",
                resource_type="entry",
                resource_id=None,
                payload_jsonb={"thread": thread_id},
                previous_hash=prev_hash,
                created_at_iso=now_iso,
            )
            entry = AuditLog(
                id=uuid.uuid4(),
                restaurant_id=rest_a_id,
                event_name=f"RACE_WRITE_{thread_id}",
                resource_type="entry",
                payload_jsonb={"thread": thread_id},
                previous_hash=prev_hash,
                record_hash=rec_hash,
                created_at=now,
            )
            session.add(entry)
            session.commit()

    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(unprotected_race_writer, 1)
        f2 = executor.submit(unprotected_race_writer, 2)
        f1.result()
        f2.result()

    # 3. verify_audit_chain must detect the broken chain (duplicate previous_hash / linkage break)
    res = verify_audit_chain(db_session, restaurant_id=rest_a_id)
    assert res["is_valid"] is False
    assert res["records_scanned"] == 3
    assert len(res["errors"]) >= 1
    error_types = [e["error_type"] for e in res["errors"]]
    assert "PREVIOUS_HASH_MISMATCH" in error_types


def test_audit_verification_cli_execution(audit_test_data, db_session: Session):
    """
    Verifies that the standalone audit verification CLI correctly reports integrity
    results, handles --restaurant-id filtering, and returns exit code 0 on valid chains
    and exit code 1 on corrupted chains.
    """
    rest_a_id = audit_test_data["rest_a"].id
    rec = record_audit_event(
        db=db_session,
        event_name="CLI_TEST_EVENT",
        resource_type="entry",
        restaurant_id=rest_a_id,
    )
    db_session.commit()

    from app.cli.verify_audit import main as cli_module_main

    # 1. Valid chain -> Exit code 0
    code_valid_all = audit_cli_main([])
    assert code_valid_all == 0

    assert cli_module_main([]) == 0

    code_valid_tenant = audit_cli_main(["--restaurant-id", str(rest_a_id)])
    assert code_valid_tenant == 0

    # 2. Invalid UUID argument -> Exit code 2
    code_invalid_uuid = audit_cli_main(["--restaurant-id", "not-a-valid-uuid"])
    assert code_invalid_uuid == 2

    # 3. Corrupted chain -> Exit code 1
    db_session.query(AuditLog).filter_by(id=rec.id).update({"record_hash": "f" * 64})
    db_session.commit()

    code_corrupt = audit_cli_main(["--restaurant-id", str(rest_a_id)])
    assert code_corrupt == 1
