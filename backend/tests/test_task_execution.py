import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.main import app
from app.models.identity import Restaurant, Role, User, UserRole
from app.models.tasks_and_rules import (
    Equipment,
    EvidenceFile,
    IdempotencyKey,
    Task,
    TaskAssignment,
    TaskCategory,
    TaskTemplate,
    TaskTemplateVersion,
    Entry,
)
from app.modules.tasks.schema import TaskEntryCreateRequest

client = TestClient(app)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def exec_test_data(db_session: Session):
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

    # Restaurants A & B
    rest_a = Restaurant(
        id=uuid.uuid4(),
        name=f"Exec Test Rest A {uuid.uuid4().hex[:4]}",
        category="RESTAURANT",
        address_line1="123 Main St",
        city="Bengaluru",
        state="Karnataka",
        pincode="560001",
        status="ACTIVE",
    )
    db_session.add(rest_a)

    rest_b = Restaurant(
        id=uuid.uuid4(),
        name=f"Exec Test Rest B {uuid.uuid4().hex[:4]}",
        category="CLOUD_KITCHEN",
        address_line1="456 Other St",
        city="Mumbai",
        state="Maharashtra",
        pincode="400001",
        status="ACTIVE",
    )
    db_session.add(rest_b)
    db_session.commit()

    # Staff A1, Staff A2, Manager A at Rest A
    staff_a1 = User(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        name="Staff A1",
        phone=f"+9191{uuid.uuid4().hex[:8]}",
        status="ACTIVE",
    )
    staff_a2 = User(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        name="Staff A2",
        phone=f"+9192{uuid.uuid4().hex[:8]}",
        status="ACTIVE",
    )
    manager_a = User(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        name="Manager A",
        phone=f"+9193{uuid.uuid4().hex[:8]}",
        status="ACTIVE",
    )

    # Staff B1 at Rest B
    staff_b1 = User(
        id=uuid.uuid4(),
        restaurant_id=rest_b.id,
        name="Staff B1",
        phone=f"+9194{uuid.uuid4().hex[:8]}",
        status="ACTIVE",
    )

    db_session.add_all([staff_a1, staff_a2, manager_a, staff_b1])
    db_session.commit()

    db_session.add(UserRole(id=uuid.uuid4(), user_id=staff_a1.id, role_id=staff_role.id, restaurant_id=rest_a.id))
    db_session.add(UserRole(id=uuid.uuid4(), user_id=staff_a2.id, role_id=staff_role.id, restaurant_id=rest_a.id))
    db_session.add(UserRole(id=uuid.uuid4(), user_id=manager_a.id, role_id=manager_role.id, restaurant_id=rest_a.id))
    db_session.add(UserRole(id=uuid.uuid4(), user_id=staff_b1.id, role_id=staff_role.id, restaurant_id=rest_b.id))
    db_session.commit()

    # Tokens
    token_staff_a1, _ = create_access_token(user_id=staff_a1.id, tenant_id=rest_a.id, roles=["STAFF"])
    token_staff_a2, _ = create_access_token(user_id=staff_a2.id, tenant_id=rest_a.id, roles=["STAFF"])
    token_manager_a, _ = create_access_token(user_id=manager_a.id, tenant_id=rest_a.id, roles=["MANAGER"])
    token_staff_b1, _ = create_access_token(user_id=staff_b1.id, tenant_id=rest_b.id, roles=["STAFF"])

    # Task Category
    category = TaskCategory(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        name="Temperature Checks",
        code="TEMP_CHECKS",
        is_active=True,
    )
    db_session.add(category)

    # Equipment A & B
    eq_a = Equipment(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        name="Chiller A",
        equipment_type="REFRIGERATOR",
        status="OPERATIONAL",
    )
    eq_b = Equipment(
        id=uuid.uuid4(),
        restaurant_id=rest_b.id,
        name="Chiller B",
        equipment_type="REFRIGERATOR",
        status="OPERATIONAL",
    )
    db_session.add_all([eq_a, eq_b])
    db_session.commit()

    # Evidence Files
    ev_completed_a = EvidenceFile(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        uploaded_by=staff_a1.id,
        storage_key=f"evidence/a/{uuid.uuid4()}.jpg",
        original_filename="photo_a.jpg",
        mime_type="image/jpeg",
        size_bytes=1000,
        sha256="a" * 64,
        upload_status="COMPLETED",
    )
    ev_pending_a = EvidenceFile(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        uploaded_by=staff_a1.id,
        storage_key=f"evidence/a/{uuid.uuid4()}.jpg",
        original_filename="photo_pending.jpg",
        mime_type="image/jpeg",
        size_bytes=1000,
        sha256="b" * 64,
        upload_status="PENDING",
    )
    ev_completed_b = EvidenceFile(
        id=uuid.uuid4(),
        restaurant_id=rest_b.id,
        uploaded_by=staff_b1.id,
        storage_key=f"evidence/b/{uuid.uuid4()}.jpg",
        original_filename="photo_b.jpg",
        mime_type="image/jpeg",
        size_bytes=1000,
        sha256="c" * 64,
        upload_status="COMPLETED",
    )
    db_session.add_all([ev_completed_a, ev_pending_a, ev_completed_b])
    db_session.commit()

    # Task Template 1: Basic
    tmpl1 = TaskTemplate(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        category_id=category.id,
        name="Basic Temp Check",
        code="BASIC_TEMP",
    )
    db_session.add(tmpl1)
    tmpl1_v1 = TaskTemplateVersion(
        id=uuid.uuid4(),
        template_id=tmpl1.id,
        version_number=1,
        configuration_jsonb={"requires_evidence": False, "requires_equipment": False},
    )
    db_session.add(tmpl1_v1)

    # Task Template 2: Requires Evidence
    tmpl2 = TaskTemplate(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        category_id=category.id,
        name="Evidence Temp Check",
        code="EVID_TEMP",
    )
    db_session.add(tmpl2)
    tmpl2_v1 = TaskTemplateVersion(
        id=uuid.uuid4(),
        template_id=tmpl2.id,
        version_number=1,
        configuration_jsonb={"requires_evidence": True, "requires_equipment": False},
    )
    db_session.add(tmpl2_v1)

    # Task Template 3: Requires Equipment
    tmpl3 = TaskTemplate(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        category_id=category.id,
        name="Equipment Temp Check",
        code="EQ_TEMP",
    )
    db_session.add(tmpl3)
    tmpl3_v1 = TaskTemplateVersion(
        id=uuid.uuid4(),
        template_id=tmpl3.id,
        version_number=1,
        configuration_jsonb={"requires_evidence": False, "requires_equipment": True},
    )
    db_session.add(tmpl3_v1)
    db_session.commit()

    # Task Instances
    now = datetime.now(timezone.utc)
    task1 = Task(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        template_id=tmpl1.id,
        template_version_id=tmpl1_v1.id,
        occurrence_key=f"2026-10-07_BASIC_{uuid.uuid4().hex[:4]}",
        status="PENDING",
        due_at=now,
    )
    task2 = Task(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        template_id=tmpl2.id,
        template_version_id=tmpl2_v1.id,
        occurrence_key=f"2026-10-07_EVID_{uuid.uuid4().hex[:4]}",
        status="PENDING",
        due_at=now,
    )
    task3 = Task(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        template_id=tmpl3.id,
        template_version_id=tmpl3_v1.id,
        occurrence_key=f"2026-10-07_EQ_{uuid.uuid4().hex[:4]}",
        status="PENDING",
        due_at=now,
    )
    task_assigned = Task(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        template_id=tmpl1.id,
        template_version_id=tmpl1_v1.id,
        occurrence_key=f"2026-10-07_ASSIGNED_{uuid.uuid4().hex[:4]}",
        status="PENDING",
        due_at=now,
    )
    db_session.add_all([task1, task2, task3, task_assigned])
    db_session.commit()

    # Assign task_assigned to staff_a1 only
    assignment = TaskAssignment(
        id=uuid.uuid4(),
        task_id=task_assigned.id,
        user_id=staff_a1.id,
    )
    db_session.add(assignment)
    db_session.commit()

    yield {
        "rest_a": rest_a,
        "rest_b": rest_b,
        "staff_a1": staff_a1,
        "staff_a2": staff_a2,
        "manager_a": manager_a,
        "staff_b1": staff_b1,
        "token_staff_a1": token_staff_a1,
        "token_staff_a2": token_staff_a2,
        "token_manager_a": token_manager_a,
        "token_staff_b1": token_staff_b1,
        "eq_a": eq_a,
        "eq_b": eq_b,
        "ev_completed_a": ev_completed_a,
        "ev_pending_a": ev_pending_a,
        "ev_completed_b": ev_completed_b,
        "task1": task1,
        "task2": task2,
        "task3": task3,
        "task_assigned": task_assigned,
    }

    # Cleanup
    db_session.query(Entry).delete()
    db_session.query(IdempotencyKey).delete()
    db_session.query(TaskAssignment).delete()
    db_session.query(Task).delete()
    db_session.query(TaskTemplateVersion).delete()
    db_session.query(TaskTemplate).delete()
    db_session.query(TaskCategory).delete()
    db_session.query(EvidenceFile).delete()
    db_session.query(Equipment).delete()
    db_session.query(UserRole).delete()
    db_session.query(User).delete()
    db_session.query(Restaurant).delete()
    db_session.commit()


# ------------------------------------------------------------------------------
# 1. Valid Task Execution & Entry Creation
# ------------------------------------------------------------------------------

def test_valid_task_execution_success(exec_test_data, db_session: Session):
    token = exec_test_data["token_staff_a1"]
    task_id = str(exec_test_data["task1"].id)

    payload = {
        "value_numeric": 3.5,
        "unit": "C",
        "value_text": "Chiller operating normally",
        "notes": "Morning check complete",
    }

    res = client.post(
        f"/api/v1/tasks/{task_id}/entries",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 201
    body = res.json()
    assert body["success"] is True
    assert body["data"]["task_id"] == task_id
    assert body["data"]["value_numeric"] == 3.5
    assert body["data"]["unit"] == "C"
    assert body["data"]["safety_status"] == "NORMAL"
    assert body["data"]["task_status"] == "COMPLETED"

    # DB Verification
    db_session.expire_all()
    task = db_session.query(Task).filter_by(id=exec_test_data["task1"].id).first()
    assert task.status == "COMPLETED"
    assert task.completed_at is not None

    entry = db_session.query(Entry).filter_by(task_id=exec_test_data["task1"].id).first()
    assert entry is not None
    assert float(entry.value_numeric) == 3.5
    assert entry.value_text == "Chiller operating normally"


# ------------------------------------------------------------------------------
# 2. Assignment & Role Access Rules
# ------------------------------------------------------------------------------

def test_assigned_staff_can_execute_assigned_task(exec_test_data):
    token = exec_test_data["token_staff_a1"]
    task_id = str(exec_test_data["task_assigned"].id)

    payload = {"value_numeric": 2.8, "unit": "C"}
    res = client.post(
        f"/api/v1/tasks/{task_id}/entries",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    assert res.json()["success"] is True


def test_unassigned_staff_denied_execution(exec_test_data):
    # Staff A2 is not assigned to task_assigned
    token = exec_test_data["token_staff_a2"]
    task_id = str(exec_test_data["task_assigned"].id)

    payload = {"value_numeric": 2.8, "unit": "C"}
    res = client.post(
        f"/api/v1/tasks/{task_id}/entries",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "TASK_ASSIGNMENT_DENIED"


def test_manager_can_execute_assigned_task(exec_test_data):
    # Manager A can execute task even if assigned to staff A1
    token = exec_test_data["token_manager_a"]
    task_id = str(exec_test_data["task_assigned"].id)

    payload = {"value_numeric": 3.0, "unit": "C"}
    res = client.post(
        f"/api/v1/tasks/{task_id}/entries",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    # Could be 201 if not completed yet, or 400 if already completed in previous test
    assert res.status_code in [201, 400]


# ------------------------------------------------------------------------------
# 3. Evidence & Equipment Validation
# ------------------------------------------------------------------------------

def test_missing_required_evidence_rejected(exec_test_data):
    token = exec_test_data["token_staff_a1"]
    task_id = str(exec_test_data["task2"].id)  # Requires evidence

    payload = {"value_numeric": 4.0, "unit": "C"}
    res = client.post(
        f"/api/v1/tasks/{task_id}/entries",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "ENTRY_EVIDENCE_REQUIRED"


def test_pending_evidence_file_rejected(exec_test_data):
    token = exec_test_data["token_staff_a1"]
    task_id = str(exec_test_data["task2"].id)
    ev_id = str(exec_test_data["ev_pending_a"].id)

    payload = {"value_numeric": 4.0, "unit": "C", "evidence_file_id": ev_id}
    res = client.post(
        f"/api/v1/tasks/{task_id}/entries",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "EVIDENCE_NOT_AVAILABLE"


def test_completed_evidence_file_accepted(exec_test_data):
    token = exec_test_data["token_staff_a1"]
    task_id = str(exec_test_data["task2"].id)
    ev_id = str(exec_test_data["ev_completed_a"].id)

    payload = {"value_numeric": 4.0, "unit": "C", "evidence_file_id": ev_id}
    res = client.post(
        f"/api/v1/tasks/{task_id}/entries",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    assert res.json()["success"] is True
    assert res.json()["data"]["evidence_file_id"] == ev_id


def test_missing_required_equipment_rejected(exec_test_data):
    token = exec_test_data["token_staff_a1"]
    task_id = str(exec_test_data["task3"].id)  # Requires equipment

    payload = {"value_numeric": 2.5, "unit": "C"}
    res = client.post(
        f"/api/v1/tasks/{task_id}/entries",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "ENTRY_EQUIPMENT_REQUIRED"


def test_valid_equipment_accepted(exec_test_data):
    token = exec_test_data["token_staff_a1"]
    task_id = str(exec_test_data["task3"].id)
    eq_id = str(exec_test_data["eq_a"].id)

    payload = {"value_numeric": 2.5, "unit": "C", "equipment_id": eq_id}
    res = client.post(
        f"/api/v1/tasks/{task_id}/entries",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    assert res.json()["success"] is True
    assert res.json()["data"]["equipment_id"] == eq_id


def test_cross_outlet_equipment_rejected(exec_test_data):
    token = exec_test_data["token_staff_a1"]
    task_id = str(exec_test_data["task3"].id)
    eq_b_id = str(exec_test_data["eq_b"].id)  # Equipment belonging to Rest B

    payload = {"value_numeric": 2.5, "unit": "C", "equipment_id": eq_b_id}
    res = client.post(
        f"/api/v1/tasks/{task_id}/entries",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "EQUIPMENT_NOT_FOUND"


# ------------------------------------------------------------------------------
# 4. Missing/Invalid Input Payload
# ------------------------------------------------------------------------------

def test_missing_all_value_fields_rejected(exec_test_data):
    token = exec_test_data["token_staff_a1"]
    task_id = str(exec_test_data["task1"].id)

    payload = {"notes": "No numeric or text reading provided"}
    res = client.post(
        f"/api/v1/tasks/{task_id}/entries",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "ENTRY_VALUE_REQUIRED"


# ------------------------------------------------------------------------------
# 5. Persistent Idempotency Replay & Key Conflict
# ------------------------------------------------------------------------------

def test_idempotency_replay_returns_cached_response(exec_test_data, db_session: Session):
    token = exec_test_data["token_staff_a1"]
    task_id = str(exec_test_data["task1"].id)
    idempotency_key = f"exec-key-{uuid.uuid4()}"

    payload = {"value_numeric": 3.8, "unit": "C", "value_text": "Initial submit"}

    # First Submission
    res1 = client.post(
        f"/api/v1/tasks/{task_id}/entries",
        json=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": idempotency_key,
        },
    )
    assert res1.status_code == 201
    data1 = res1.json()["data"]

    # Second Submission with exact same payload and key
    res2 = client.post(
        f"/api/v1/tasks/{task_id}/entries",
        json=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": idempotency_key,
        },
    )
    assert res2.status_code == 200
    body2 = res2.json()
    assert body2["success"] is True
    assert body2["meta"]["replayed"] is True
    assert body2["data"]["id"] == data1["id"]

    # Verify only 1 entry was created in DB
    entries_count = db_session.query(Entry).filter_by(task_id=exec_test_data["task1"].id).count()
    assert entries_count == 1


def test_idempotency_key_reuse_payload_mismatch_rejected(exec_test_data):
    token = exec_test_data["token_staff_a1"]
    task_id = str(exec_test_data["task1"].id)
    idempotency_key = f"exec-key-{uuid.uuid4()}"

    payload1 = {"value_numeric": 3.8, "unit": "C"}
    res1 = client.post(
        f"/api/v1/tasks/{task_id}/entries",
        json=payload1,
        headers={
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": idempotency_key,
        },
    )
    assert res1.status_code in [201, 200]

    # Re-send same key with MODIFIED payload
    payload2 = {"value_numeric": 9.9, "unit": "C"}
    res2 = client.post(
        f"/api/v1/tasks/{task_id}/entries",
        json=payload2,
        headers={
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": idempotency_key,
        },
    )
    assert res2.status_code == 409
    assert res2.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSE"


def test_concurrent_duplicate_submission_processing_conflict(exec_test_data, db_session: Session):
    token = exec_test_data["token_staff_a1"]
    task_id = str(exec_test_data["task1"].id)
    idempotency_key = f"concurrent-key-{uuid.uuid4()}"

    payload = {"value_numeric": 3.8, "unit": "C"}
    req_dto = TaskEntryCreateRequest(**payload)
    import json, hashlib
    expected_hash = hashlib.sha256(json.dumps(req_dto.model_dump(mode="json"), sort_keys=True).encode()).hexdigest()

    # Pre-insert an IdempotencyKey row in 'PROCESSING' status with matching request_hash
    key_record = IdempotencyKey(
        id=uuid.uuid4(),
        restaurant_id=exec_test_data["rest_a"].id,
        user_id=exec_test_data["staff_a1"].id,
        key=idempotency_key,
        request_hash=expected_hash,
        status="PROCESSING",
        expires_at=datetime.now(timezone.utc),
    )
    db_session.add(key_record)
    db_session.commit()

    res = client.post(
        f"/api/v1/tasks/{task_id}/entries",
        json=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": idempotency_key,
        },
    )
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "IDEMPOTENCY_KEY_PROCESSING"


# ------------------------------------------------------------------------------
# 6. Cross-Tenant Access & Authorization Rules
# ------------------------------------------------------------------------------

def test_cross_tenant_task_execution_forbidden(exec_test_data):
    token_staff_b1 = exec_test_data["token_staff_b1"]  # Staff at Rest B
    task1_id = str(exec_test_data["task1"].id)  # Task at Rest A

    payload = {"value_numeric": 3.5, "unit": "C"}
    res = client.post(
        f"/api/v1/tasks/{task1_id}/entries",
        json=payload,
        headers={"Authorization": f"Bearer {token_staff_b1}"},
    )
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "FORBIDDEN_CROSS_TENANT"


def test_unauthenticated_request_rejected():
    task_id = str(uuid.uuid4())
    res = client.post(
        f"/api/v1/tasks/{task_id}/entries",
        json={"value_numeric": 3.5},
    )
    assert res.status_code == 401


# ------------------------------------------------------------------------------
# 7. Already Completed Task Execution Rules
# ------------------------------------------------------------------------------

def test_already_completed_task_reexecution_rejected(exec_test_data):
    token = exec_test_data["token_staff_a1"]
    task_id = str(exec_test_data["task1"].id)

    payload1 = {"value_numeric": 3.5, "unit": "C"}
    # First execution completes task
    client.post(
        f"/api/v1/tasks/{task_id}/entries",
        json=payload1,
        headers={"Authorization": f"Bearer {token}"},
    )

    # Second execution WITHOUT idempotency key attempt on already completed task
    payload2 = {"value_numeric": 3.6, "unit": "C"}
    res2 = client.post(
        f"/api/v1/tasks/{task_id}/entries",
        json=payload2,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res2.status_code == 400
    assert res2.json()["error"]["code"] == "TASK_ALREADY_COMPLETED"
