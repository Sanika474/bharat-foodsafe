import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.audit import (
    GENESIS_PREVIOUS_HASH,
    compute_record_hash,
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
    db_session.add_all([staff_a1, manager_a, staff_b1])
    db_session.commit()

    db_session.add(UserRole(id=uuid.uuid4(), user_id=staff_a1.id, role_id=staff_role.id, restaurant_id=rest_a.id))
    db_session.add(UserRole(id=uuid.uuid4(), user_id=manager_a.id, role_id=manager_role.id, restaurant_id=rest_a.id))
    db_session.add(UserRole(id=uuid.uuid4(), user_id=staff_b1.id, role_id=staff_role.id, restaurant_id=rest_b.id))
    db_session.commit()

    token_staff_a1, _ = create_access_token(user_id=staff_a1.id, tenant_id=rest_a.id, roles=["STAFF"])
    token_manager_a, _ = create_access_token(user_id=manager_a.id, tenant_id=rest_a.id, roles=["MANAGER"])
    token_staff_b1, _ = create_access_token(user_id=staff_b1.id, tenant_id=rest_b.id, roles=["STAFF"])

    yield {
        "rest_a": rest_a,
        "rest_b": rest_b,
        "staff_a1": staff_a1,
        "manager_a": manager_a,
        "staff_b1": staff_b1,
        "token_staff_a1": token_staff_a1,
        "token_manager_a": token_manager_a,
        "token_staff_b1": token_staff_b1,
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
    rec1 = record_audit_event(db=db_session, event_name="EVENT_1", resource_type="type1", restaurant_id=rest_id, user_id=user_id)
    rec2 = record_audit_event(db=db_session, event_name="EVENT_2", resource_type="type2", restaurant_id=rest_id, user_id=user_id)
    rec3 = record_audit_event(db=db_session, event_name="EVENT_3", resource_type="type3", restaurant_id=rest_id, user_id=user_id)
    rec4 = record_audit_event(db=db_session, event_name="EVENT_4", resource_type="type4", restaurant_id=rest_id, user_id=user_id)
    rec5 = record_audit_event(db=db_session, event_name="EVENT_5", resource_type="type5", restaurant_id=rest_id, user_id=user_id)
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

    rec_a1 = record_audit_event(db=db_session, event_name="EVENT_A1", resource_type="entry", restaurant_id=rest_a_id)
    rec_b1 = record_audit_event(db=db_session, event_name="EVENT_B1", resource_type="entry", restaurant_id=rest_b_id)
    rec_a2 = record_audit_event(db=db_session, event_name="EVENT_A2", resource_type="entry", restaurant_id=rest_a_id)
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


# ------------------------------------------------------------------------------
# 4. Immutability & Transaction Rollback
# ------------------------------------------------------------------------------

def test_audit_log_immutability_update_blocked(audit_test_data, db_session: Session):
    rec = record_audit_event(db=db_session, event_name="EVENT_ORIGINAL", resource_type="entry", restaurant_id=audit_test_data["rest_a"].id)
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
        record_audit_event(db=db_session, event_name="EVENT_TRANSIENT", resource_type="entry", restaurant_id=rest_id)
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

    record_audit_event(db=db_session, event_name="EVENT_1", resource_type="entry", restaurant_id=rest_id, payload_jsonb={"temp": 3.5})
    rec2 = record_audit_event(db=db_session, event_name="EVENT_2", resource_type="entry", restaurant_id=rest_id, payload_jsonb={"temp": 4.0})
    db_session.commit()

    # Directly mutate database payload behind the scenes
    db_session.execute(
        AuditLog.__table__.update().where(AuditLog.id == rec2.id).values(payload_jsonb={"temp": 99.9})
    )
    db_session.commit()
    db_session.expire_all()

    res = verify_audit_chain(db_session, restaurant_id=rest_id)
    assert res["is_valid"] is False
    assert len(res["errors"]) > 0
    assert any(e["error_type"] == "TAMPERED_RECORD_HASH" for e in res["errors"])


def test_tampered_hash_and_broken_link_detection(audit_test_data, db_session: Session):
    rest_id = audit_test_data["rest_a"].id

    rec1 = record_audit_event(db=db_session, event_name="EVENT_1", resource_type="entry", restaurant_id=rest_id)
    rec2 = record_audit_event(db=db_session, event_name="EVENT_2", resource_type="entry", restaurant_id=rest_id)
    rec3 = record_audit_event(db=db_session, event_name="EVENT_3", resource_type="entry", restaurant_id=rest_id)
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
    record_audit_event(db=db_session, event_name="EVENT_API_TEST", resource_type="entry", restaurant_id=rest_id)
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
    record_audit_event(db=db_session, event_name="EVENT_API_VERIFY", resource_type="entry", restaurant_id=rest_id)
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
    rec = record_audit_event(db=db_session, event_name="EVENT_IMMUTABLE", resource_type="entry", restaurant_id=audit_test_data["rest_a"].id)
    db_session.commit()

    token_mgr = audit_test_data["token_manager_a"]
    res = client.delete(
        f"/api/v1/audit/logs/{rec.id}",
        headers={"Authorization": f"Bearer {token_mgr}"},
    )
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "AUDIT_LOG_IMMUTABLE"
