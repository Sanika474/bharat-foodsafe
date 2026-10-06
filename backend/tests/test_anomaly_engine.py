import uuid
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.main import app
from app.models.analytics_and_incidents import AnomalyResult
from app.models.identity import Restaurant, Role, User, UserRole
from app.models.notifications_and_audit import AuditLog
from app.models.tasks_and_rules import (
    EvidenceFile,
    Task,
    TaskCategory,
    TaskTemplate,
    TaskTemplateVersion,
    Entry,
)
from app.modules.anomaly import service as anomaly_service

client = TestClient(app)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def anomaly_test_data(db_session: Session):
    # Roles
    staff_role = db_session.query(Role).filter_by(name="STAFF").first()
    if not staff_role:
        staff_role = Role(id=uuid.uuid4(), name="STAFF", is_system_role=True)
        db_session.add(staff_role)

    manager_role = db_session.query(Role).filter_by(name="MANAGER").first()
    if not manager_role:
        manager_role = Role(id=uuid.uuid4(), name="MANAGER", is_system_role=True)
        db_session.add(manager_role)

    db_session.commit()

    # Restaurants A & B
    rest_a = Restaurant(
        id=uuid.uuid4(),
        name=f"Anomaly Rest A {uuid.uuid4().hex[:4]}",
        category="RESTAURANT",
        address_line1="100 Anomaly Ave",
        city="Bengaluru",
        state="Karnataka",
        pincode="560001",
        status="ACTIVE",
    )
    rest_b = Restaurant(
        id=uuid.uuid4(),
        name=f"Anomaly Rest B {uuid.uuid4().hex[:4]}",
        category="CLOUD_KITCHEN",
        address_line1="200 Isolation St",
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
        name="Anomaly Staff A1",
        phone=f"+9161{uuid.uuid4().hex[:8]}",
        status="ACTIVE",
    )
    manager_a = User(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        name="Anomaly Manager A",
        phone=f"+9162{uuid.uuid4().hex[:8]}",
        status="ACTIVE",
    )
    staff_b1 = User(
        id=uuid.uuid4(),
        restaurant_id=rest_b.id,
        name="Anomaly Staff B1",
        phone=f"+9163{uuid.uuid4().hex[:8]}",
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

    # Task Template & Version
    cat = TaskCategory(id=uuid.uuid4(), restaurant_id=rest_a.id, name="General", code=f"GEN_{uuid.uuid4().hex[:4]}")
    db_session.add(cat)
    db_session.commit()

    tmpl = TaskTemplate(id=uuid.uuid4(), restaurant_id=rest_a.id, category_id=cat.id, name="Chiller Log", code=f"LOG_{uuid.uuid4().hex[:4]}")
    db_session.add(tmpl)
    db_session.commit()

    tmpl_v = TaskTemplateVersion(id=uuid.uuid4(), template_id=tmpl.id, version_number=1, configuration_jsonb={})
    db_session.add(tmpl_v)
    db_session.commit()

    now = datetime.now(timezone.utc)
    task1 = Task(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        template_id=tmpl.id,
        template_version_id=tmpl_v.id,
        occurrence_key=f"2026-10-07_ANOM_{uuid.uuid4().hex[:4]}",
        status="PENDING",
        due_at=now,
    )
    db_session.add(task1)
    db_session.commit()

    # Shared Evidence File
    ev = EvidenceFile(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        uploaded_by=staff_a1.id,
        storage_key=f"evidence/{uuid.uuid4()}.jpg",
        original_filename="reuse.jpg",
        mime_type="image/jpeg",
        size_bytes=1000,
        sha256="d" * 64,
        upload_status="COMPLETED",
    )
    db_session.add(ev)
    db_session.commit()

    yield {
        "rest_a": rest_a,
        "rest_b": rest_b,
        "staff_a1": staff_a1,
        "manager_a": manager_a,
        "staff_b1": staff_b1,
        "token_staff_a1": token_staff_a1,
        "token_manager_a": token_manager_a,
        "token_staff_b1": token_staff_b1,
        "task1": task1,
        "evidence": ev,
    }

    # Cleanup
    db_session.query(AnomalyResult).delete()
    db_session.query(AuditLog).delete()
    db_session.query(Entry).delete()
    db_session.query(EvidenceFile).delete()
    db_session.query(Task).delete()
    db_session.query(TaskTemplateVersion).delete()
    db_session.query(TaskTemplate).delete()
    db_session.query(TaskCategory).delete()
    db_session.commit()


# Helper to seed dummy entry history
def seed_entry_history(db: Session, restaurant_id: uuid.UUID, user_id: uuid.UUID, task_id: uuid.UUID, count: int = 35):
    now = datetime.now(timezone.utc)
    entries = []
    for i in range(count):
        # Vary temperatures slightly (e.g. 2.0 to 4.5) and spread over time with timestamp variance
        val = 2.0 + (i % 5) * 0.5
        # Add random-like minute variance so std dev of diffs > 0.2s (avoiding false robotic timing flag)
        minute_offset = (count - i) * 30 + (i % 7) * 3 + (i % 3) * 11
        t_time = now - timedelta(minutes=minute_offset)
        e = Entry(
            id=uuid.uuid4(),
            restaurant_id=restaurant_id,
            task_id=task_id,
            user_id=user_id,
            value_numeric=val,
            unit="C",
            safety_status="NORMAL",
            created_at=t_time,
        )
        entries.append(e)
    db.add_all(entries)
    db.commit()
    return entries


# ------------------------------------------------------------------------------
# 1. Cold-Start Policy (< 30 entries)
# ------------------------------------------------------------------------------

def test_cold_start_policy_returns_unavailable(anomaly_test_data, db_session: Session):
    rest_id = anomaly_test_data["rest_a"].id
    user_id = anomaly_test_data["staff_a1"].id
    task_id = anomaly_test_data["task1"].id

    # Create only 5 entries (< 30)
    seed_entry_history(db_session, rest_id, user_id, task_id, count=5)

    latest_entry = Entry(
        id=uuid.uuid4(),
        restaurant_id=rest_id,
        task_id=task_id,
        user_id=user_id,
        value_numeric=3.0,
        unit="C",
        safety_status="NORMAL",
    )
    db_session.add(latest_entry)
    db_session.commit()

    res = anomaly_service.evaluate_entry_anomaly(db_session, latest_entry, user_id=user_id)
    db_session.commit()

    assert res.decision == "UNAVAILABLE"
    assert res.ml_score is None
    assert res.reasons_jsonb["analysis_status"] == "UNAVAILABLE"
    assert "Insufficient entry history" in res.reasons_jsonb["reason"]


# ------------------------------------------------------------------------------
# 2. Normal Shift (No False Positive)
# ------------------------------------------------------------------------------

def test_normal_operating_shift_returns_no_flag(anomaly_test_data, db_session: Session):
    rest_id = anomaly_test_data["rest_a"].id
    user_id = anomaly_test_data["staff_a1"].id
    task_id = anomaly_test_data["task1"].id

    # Seed 35 normal entries
    seed_entry_history(db_session, rest_id, user_id, task_id, count=35)

    now = datetime.now(timezone.utc)
    entry = Entry(
        id=uuid.uuid4(),
        restaurant_id=rest_id,
        task_id=task_id,
        user_id=user_id,
        value_numeric=3.2,
        unit="C",
        safety_status="NORMAL",
        created_at=now,
    )
    db_session.add(entry)
    db_session.commit()

    res = anomaly_service.evaluate_entry_anomaly(db_session, entry, user_id=user_id)
    db_session.commit()

    assert res.decision == "NO_FLAG"
    assert res.ml_score is not None
    assert res.ml_score < 0.40


# ------------------------------------------------------------------------------
# 3. Anomaly Conditions (Burst, Photo Reuse, Flatlining)
# ------------------------------------------------------------------------------

def test_rapid_burst_submission_flagged(anomaly_test_data, db_session: Session):
    rest_id = anomaly_test_data["rest_a"].id
    user_id = anomaly_test_data["staff_a1"].id
    task_id = anomaly_test_data["task1"].id

    seed_entry_history(db_session, rest_id, user_id, task_id, count=35)

    # Submit 6 entries in the exact same minute
    now = datetime.now(timezone.utc)
    burst_entries = []
    for _ in range(6):
        e = Entry(
            id=uuid.uuid4(),
            restaurant_id=rest_id,
            task_id=task_id,
            user_id=user_id,
            value_numeric=3.0,
            unit="C",
            safety_status="NORMAL",
            created_at=now,
        )
        burst_entries.append(e)
    db_session.add_all(burst_entries)
    db_session.commit()

    res = anomaly_service.evaluate_entry_anomaly(db_session, burst_entries[-1], user_id=user_id)
    db_session.commit()

    assert res.decision in ("REVIEW", "SUSPICIOUS", "ESCALATE")
    flags = res.reasons_jsonb.get("flags", [])
    assert any("burst" in f.lower() for f in flags)

    # Check audit log record created for flagged anomaly
    audit_record = db_session.query(AuditLog).filter_by(event_name="ANOMALY_FLAGGED").first()
    assert audit_record is not None
    assert audit_record.resource_id == res.id


def test_photo_evidence_reuse_flagged(anomaly_test_data, db_session: Session):
    rest_id = anomaly_test_data["rest_a"].id
    user_id = anomaly_test_data["staff_a1"].id
    task_id = anomaly_test_data["task1"].id
    ev_id = anomaly_test_data["evidence"].id

    seed_entry_history(db_session, rest_id, user_id, task_id, count=35)

    # 2 entries with exact same evidence_file_id
    e1 = Entry(id=uuid.uuid4(), restaurant_id=rest_id, task_id=task_id, user_id=user_id, evidence_file_id=ev_id, value_numeric=3.0, unit="C", safety_status="NORMAL")
    e2 = Entry(id=uuid.uuid4(), restaurant_id=rest_id, task_id=task_id, user_id=user_id, evidence_file_id=ev_id, value_numeric=3.1, unit="C", safety_status="NORMAL")
    db_session.add_all([e1, e2])
    db_session.commit()

    res = anomaly_service.evaluate_entry_anomaly(db_session, e2, user_id=user_id)
    db_session.commit()

    assert res.decision in ("REVIEW", "SUSPICIOUS", "ESCALATE")
    flags = res.reasons_jsonb.get("flags", [])
    assert any("photo" in f.lower() or "reuse" in f.lower() for f in flags)


# ------------------------------------------------------------------------------
# 4. Duplicate Prevention & Deterministic Re-run
# ------------------------------------------------------------------------------

def test_duplicate_anomaly_evaluation_prevented(anomaly_test_data, db_session: Session):
    rest_id = anomaly_test_data["rest_a"].id
    user_id = anomaly_test_data["staff_a1"].id
    task_id = anomaly_test_data["task1"].id

    seed_entry_history(db_session, rest_id, user_id, task_id, count=35)

    entry = Entry(id=uuid.uuid4(), restaurant_id=rest_id, task_id=task_id, user_id=user_id, value_numeric=3.0, unit="C", safety_status="NORMAL")
    db_session.add(entry)
    db_session.commit()

    res1 = anomaly_service.evaluate_entry_anomaly(db_session, entry, user_id=user_id)
    db_session.commit()

    res2 = anomaly_service.evaluate_entry_anomaly(db_session, entry, user_id=user_id)
    db_session.commit()

    assert res1.id == res2.id

    count = db_session.query(AnomalyResult).filter_by(entry_id=entry.id).count()
    assert count == 1


# ------------------------------------------------------------------------------
# 5. API Authorization & Endpoints
# ------------------------------------------------------------------------------

def test_api_list_anomalies_manager_allowed(anomaly_test_data, db_session: Session):
    rest_id = anomaly_test_data["rest_a"].id
    user_id = anomaly_test_data["staff_a1"].id
    task_id = anomaly_test_data["task1"].id

    seed_entry_history(db_session, rest_id, user_id, task_id, count=35)

    entry = Entry(id=uuid.uuid4(), restaurant_id=rest_id, task_id=task_id, user_id=user_id, value_numeric=3.0, unit="C", safety_status="NORMAL")
    db_session.add(entry)
    db_session.commit()

    anomaly_service.evaluate_entry_anomaly(db_session, entry, user_id=user_id)
    db_session.commit()

    token_mgr = anomaly_test_data["token_manager_a"]
    res = client.get(
        "/api/v1/anomalies",
        headers={"Authorization": f"Bearer {token_mgr}"},
    )
    assert res.status_code == 200
    assert res.json()["success"] is True
    assert res.json()["data"]["total"] >= 1


def test_api_list_anomalies_staff_denied(anomaly_test_data):
    token_staff = anomaly_test_data["token_staff_a1"]
    res = client.get(
        "/api/v1/anomalies",
        headers={"Authorization": f"Bearer {token_staff}"},
    )
    assert res.status_code == 403


def test_api_analyze_entry_endpoint(anomaly_test_data, db_session: Session):
    rest_id = anomaly_test_data["rest_a"].id
    user_id = anomaly_test_data["staff_a1"].id
    task_id = anomaly_test_data["task1"].id

    seed_entry_history(db_session, rest_id, user_id, task_id, count=35)

    entry = Entry(id=uuid.uuid4(), restaurant_id=rest_id, task_id=task_id, user_id=user_id, value_numeric=3.0, unit="C", safety_status="NORMAL")
    db_session.add(entry)
    db_session.commit()

    token_mgr = anomaly_test_data["token_manager_a"]
    res = client.post(
        f"/api/v1/anomalies/analyze/{entry.id}",
        headers={"Authorization": f"Bearer {token_mgr}"},
    )
    assert res.status_code == 200
    assert res.json()["success"] is True
    assert res.json()["data"]["entry_id"] == str(entry.id)


def test_cross_tenant_anomaly_access_forbidden(anomaly_test_data, db_session: Session):
    rest_a_id = anomaly_test_data["rest_a"].id
    user_id = anomaly_test_data["staff_a1"].id
    task_id = anomaly_test_data["task1"].id

    seed_entry_history(db_session, rest_a_id, user_id, task_id, count=35)

    entry = Entry(id=uuid.uuid4(), restaurant_id=rest_a_id, task_id=task_id, user_id=user_id, value_numeric=3.0, unit="C", safety_status="NORMAL")
    db_session.add(entry)
    db_session.commit()

    anom = anomaly_service.evaluate_entry_anomaly(db_session, entry, user_id=user_id)
    db_session.commit()

    token_b = anomaly_test_data["token_staff_b1"]
    res = client.get(
        f"/api/v1/anomalies/{anom.id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert res.status_code == 403
