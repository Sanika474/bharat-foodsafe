import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.main import app
from app.models.analytics_and_incidents import CorrectiveAction, Incident
from app.models.identity import Restaurant, Role, User, UserRole
from app.models.tasks_and_rules import (
    Equipment,
    EvidenceFile,
    RuleSource,
    SafetyRule,
    SafetyRuleBinding,
    Task,
    TaskAssignment,
    TaskCategory,
    TaskTemplate,
    TaskTemplateVersion,
    Entry,
    EntrySafetyEvaluation,
)

client = TestClient(app)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def incident_test_data(db_session: Session):
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

    # Create Restaurants
    rest_a = Restaurant(
        id=uuid.uuid4(),
        name=f"Incident Test Rest A {uuid.uuid4().hex[:4]}",
        category="RESTAURANT",
        address_line1="100 Food Safety Way",
        city="Bengaluru",
        state="Karnataka",
        pincode="560001",
        status="ACTIVE",
    )
    rest_b = Restaurant(
        id=uuid.uuid4(),
        name=f"Incident Test Rest B {uuid.uuid4().hex[:4]}",
        category="CLOUD_KITCHEN",
        address_line1="200 Isolation Rd",
        city="Mumbai",
        state="Maharashtra",
        pincode="400001",
        status="ACTIVE",
    )
    db_session.add_all([rest_a, rest_b])
    db_session.commit()

    # Create Users
    staff_a1 = User(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        name="Staff A1",
        phone=f"+9181{uuid.uuid4().hex[:8]}",
        status="ACTIVE",
    )
    staff_a2 = User(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        name="Staff A2",
        phone=f"+9182{uuid.uuid4().hex[:8]}",
        status="ACTIVE",
    )
    manager_a = User(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        name="Manager A",
        phone=f"+9183{uuid.uuid4().hex[:8]}",
        status="ACTIVE",
    )
    staff_b1 = User(
        id=uuid.uuid4(),
        restaurant_id=rest_b.id,
        name="Staff B1",
        phone=f"+9184{uuid.uuid4().hex[:8]}",
        status="ACTIVE",
    )
    db_session.add_all([staff_a1, staff_a2, manager_a, staff_b1])
    db_session.commit()

    db_session.add(UserRole(id=uuid.uuid4(), user_id=staff_a1.id, role_id=staff_role.id, restaurant_id=rest_a.id))
    db_session.add(UserRole(id=uuid.uuid4(), user_id=staff_a2.id, role_id=staff_role.id, restaurant_id=rest_a.id))
    db_session.add(UserRole(id=uuid.uuid4(), user_id=manager_a.id, role_id=manager_role.id, restaurant_id=rest_a.id))
    db_session.add(UserRole(id=uuid.uuid4(), user_id=staff_b1.id, role_id=staff_role.id, restaurant_id=rest_b.id))
    db_session.commit()

    # JWT Tokens
    token_staff_a1, _ = create_access_token(user_id=staff_a1.id, tenant_id=rest_a.id, roles=["STAFF"])
    token_staff_a2, _ = create_access_token(user_id=staff_a2.id, tenant_id=rest_a.id, roles=["STAFF"])
    token_manager_a, _ = create_access_token(user_id=manager_a.id, tenant_id=rest_a.id, roles=["MANAGER"])
    token_staff_b1, _ = create_access_token(user_id=staff_b1.id, tenant_id=rest_b.id, roles=["STAFF"])

    # Rule Source
    rule_source = RuleSource(
        id=uuid.uuid4(),
        source_code=f"FSSAI_INC_{uuid.uuid4().hex[:4]}",
        title="FSSAI Guidelines",
        issuing_authority="FSSAI",
        review_status="VERIFIED",
    )
    db_session.add(rule_source)

    # Safety Rule: Chiller Temp (Normal: <= 4.0, Deviation: 4.1-7.0, Critical: > 7.0)
    safety_rule = SafetyRule(
        id=uuid.uuid4(),
        rule_source_id=rule_source.id,
        rule_code=f"CHILLER_MAX_TEMP_{uuid.uuid4().hex[:4]}",
        version_number=1,
        name="Chiller Cold Storage Thresholds",
        description="Cold holding must remain below 4°C. Above 7°C is CRITICAL.",
        condition_jsonb={
            "field": "value_numeric",
            "normal": {"lte": 4.0},
            "deviation": {"gt": 4.0, "lte": 7.0},
            "critical": {"gt": 7.0},
        },
        action_jsonb={"default_severity": "CRITICAL"},
        is_active=True,
    )
    db_session.add(safety_rule)
    db_session.commit()

    # Task Setup
    category = TaskCategory(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        name="Temperature Checks",
        code=f"INC_TEMP_{uuid.uuid4().hex[:4]}",
        is_active=True,
    )
    db_session.add(category)
    db_session.commit()

    tmpl = TaskTemplate(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        category_id=category.id,
        name="Chiller Temp Log",
        code=f"CHILLER_LOG_{uuid.uuid4().hex[:4]}",
    )
    db_session.add(tmpl)
    db_session.commit()

    tmpl_version = TaskTemplateVersion(
        id=uuid.uuid4(),
        template_id=tmpl.id,
        version_number=1,
        configuration_jsonb={"requires_evidence": False, "requires_equipment": False},
    )
    db_session.add(tmpl_version)
    db_session.commit()

    # Bind Rule to Template
    binding = SafetyRuleBinding(
        id=uuid.uuid4(),
        template_id=tmpl.id,
        safety_rule_id=safety_rule.id,
    )
    db_session.add(binding)
    db_session.commit()

    # Tasks
    now = datetime.now(timezone.utc)
    task1 = Task(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        template_id=tmpl.id,
        template_version_id=tmpl_version.id,
        occurrence_key=f"2026-10-07_INC_TASK1_{uuid.uuid4().hex[:4]}",
        status="PENDING",
        due_at=now,
    )
    task2 = Task(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        template_id=tmpl.id,
        template_version_id=tmpl_version.id,
        occurrence_key=f"2026-10-07_INC_TASK2_{uuid.uuid4().hex[:4]}",
        status="PENDING",
        due_at=now,
    )
    task3 = Task(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        template_id=tmpl.id,
        template_version_id=tmpl_version.id,
        occurrence_key=f"2026-10-07_INC_TASK3_{uuid.uuid4().hex[:4]}",
        status="PENDING",
        due_at=now,
    )
    db_session.add_all([task1, task2, task3])
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
        "safety_rule": safety_rule,
        "task1": task1,
        "task2": task2,
        "task3": task3,
    }

    # Cleanup
    db_session.query(CorrectiveAction).delete()
    db_session.query(Incident).delete()
    db_session.query(EntrySafetyEvaluation).delete()
    db_session.query(Entry).delete()
    db_session.query(TaskAssignment).delete()
    db_session.query(Task).delete()
    db_session.query(SafetyRuleBinding).delete()
    db_session.query(TaskTemplateVersion).delete()
    db_session.query(TaskTemplate).delete()
    db_session.query(TaskCategory).delete()
    db_session.query(SafetyRule).delete()
    db_session.query(RuleSource).delete()
    db_session.query(UserRole).delete()
    db_session.query(User).delete()
    db_session.query(Restaurant).delete()
    db_session.commit()


# ------------------------------------------------------------------------------
# 1. Automatic CRITICAL -> Incident & CAPA Creation
# ------------------------------------------------------------------------------

def test_automatic_critical_incident_creation(incident_test_data, db_session: Session):
    token = incident_test_data["token_staff_a1"]
    task_id = str(incident_test_data["task1"].id)

    # Submit CRITICAL reading (9.5 °C > 7.0 °C)
    payload = {"value_numeric": 9.5, "unit": "C", "value_text": "Compressor failure"}
    res = client.post(
        f"/api/v1/tasks/{task_id}/entries",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 201
    entry_id = res.json()["data"]["id"]
    assert res.json()["data"]["safety_status"] == "CRITICAL"

    # Verify Incident created
    db_session.expire_all()
    inc = db_session.query(Incident).filter_by(entry_id=entry_id).first()
    assert inc is not None
    assert inc.status == "OPEN"
    assert inc.severity == "CRITICAL"
    assert "CRITICAL SAFETY DEVIATION" in inc.title

    # Verify Corrective Action (CAPA) created
    cas = db_session.query(CorrectiveAction).filter_by(incident_id=inc.id).all()
    assert len(cas) == 1
    ca = cas[0]
    assert ca.status == "PENDING"
    assert ca.assigned_to is None


# ------------------------------------------------------------------------------
# 2. NORMAL & DEVIATION Do Not Create Incidents
# ------------------------------------------------------------------------------

def test_normal_reading_does_not_create_incident(incident_test_data, db_session: Session):
    token = incident_test_data["token_staff_a1"]
    task_id = str(incident_test_data["task2"].id)

    # Submit NORMAL reading (3.0 °C <= 4.0 °C)
    payload = {"value_numeric": 3.0, "unit": "C"}
    res = client.post(
        f"/api/v1/tasks/{task_id}/entries",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    entry_id = res.json()["data"]["id"]
    assert res.json()["data"]["safety_status"] == "NORMAL"

    inc = db_session.query(Incident).filter_by(entry_id=entry_id).first()
    assert inc is None


def test_deviation_reading_does_not_create_incident(incident_test_data, db_session: Session):
    token = incident_test_data["token_staff_a1"]
    task_id = str(incident_test_data["task3"].id)

    # Submit DEVIATION reading (5.5 °C is between 4.0 and 7.0)
    payload = {"value_numeric": 5.5, "unit": "C"}
    res = client.post(
        f"/api/v1/tasks/{task_id}/entries",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    entry_id = res.json()["data"]["id"]
    assert res.json()["data"]["safety_status"] == "DEVIATION"

    inc = db_session.query(Incident).filter_by(entry_id=entry_id).first()
    assert inc is None


# ------------------------------------------------------------------------------
# 3. Duplicate Prevention & Idempotency
# ------------------------------------------------------------------------------

def test_duplicate_incident_creation_prevented(incident_test_data, db_session: Session):
    from app.modules.incidents import service as inc_service

    # Create a dummy entry
    entry = Entry(
        id=uuid.uuid4(),
        restaurant_id=incident_test_data["rest_a"].id,
        task_id=incident_test_data["task1"].id,
        user_id=incident_test_data["staff_a1"].id,
        value_numeric=10.0,
        unit="C",
        safety_status="CRITICAL",
    )
    db_session.add(entry)
    db_session.commit()

    # Trigger incident creation twice for same entry
    inc1 = inc_service.trigger_critical_deviation_incident(db_session, entry, incident_test_data["task1"])
    inc2 = inc_service.trigger_critical_deviation_incident(db_session, entry, incident_test_data["task1"])

    assert inc1.id == inc2.id

    count = db_session.query(Incident).filter_by(entry_id=entry.id).count()
    assert count == 1


# ------------------------------------------------------------------------------
# 4. Manager Assignment of CAPA
# ------------------------------------------------------------------------------

def test_manager_assignment_of_capa_success(incident_test_data, db_session: Session):
    # Create incident + CAPA
    token_staff = incident_test_data["token_staff_a1"]
    task_id = str(incident_test_data["task1"].id)

    res = client.post(
        f"/api/v1/tasks/{task_id}/entries",
        json={"value_numeric": 8.5, "unit": "C"},
        headers={"Authorization": f"Bearer {token_staff}"},
    )
    entry_id = res.json()["data"]["id"]
    inc = db_session.query(Incident).filter_by(entry_id=entry_id).first()
    ca = db_session.query(CorrectiveAction).filter_by(incident_id=inc.id).first()

    # Manager assigns CAPA to Staff A2
    token_manager = incident_test_data["token_manager_a"]
    staff_a2_id = str(incident_test_data["staff_a2"].id)

    assign_res = client.post(
        f"/api/v1/corrective-actions/{ca.id}/assign",
        json={"assigned_to": staff_a2_id, "action_text": "Adjust chiller thermostat and re-check in 15 mins."},
        headers={"Authorization": f"Bearer {token_manager}"},
    )
    assert assign_res.status_code == 200
    ca_data = assign_res.json()["data"]
    assert ca_data["status"] == "IN_PROGRESS"
    assert ca_data["assigned_to"] == staff_a2_id

    # Verify Incident status updated to INVESTIGATING
    inc_res = client.get(
        f"/api/v1/incidents/{inc.id}",
        headers={"Authorization": f"Bearer {token_manager}"},
    )
    assert inc_res.status_code == 200
    assert inc_res.json()["data"]["status"] == "INVESTIGATING"


def test_staff_cannot_assign_capa(incident_test_data, db_session: Session):
    token_staff = incident_test_data["token_staff_a1"]
    task_id = str(incident_test_data["task1"].id)

    res = client.post(
        f"/api/v1/tasks/{task_id}/entries",
        json={"value_numeric": 8.5, "unit": "C"},
        headers={"Authorization": f"Bearer {token_staff}"},
    )
    entry_id = res.json()["data"]["id"]
    inc = db_session.query(Incident).filter_by(entry_id=entry_id).first()
    ca = db_session.query(CorrectiveAction).filter_by(incident_id=inc.id).first()

    # Staff tries to assign
    assign_res = client.post(
        f"/api/v1/corrective-actions/{ca.id}/assign",
        json={"assigned_to": str(incident_test_data["staff_a2"].id)},
        headers={"Authorization": f"Bearer {token_staff}"},
    )
    assert assign_res.status_code == 403


# ------------------------------------------------------------------------------
# 5. Staff Corrective Action & Recheck Workflow
# ------------------------------------------------------------------------------

def test_staff_complete_recheck_success(incident_test_data, db_session: Session):
    token_staff1 = incident_test_data["token_staff_a1"]
    token_staff2 = incident_test_data["token_staff_a2"]
    token_manager = incident_test_data["token_manager_a"]

    # 1. Staff 1 triggers critical entry
    res = client.post(
        f"/api/v1/tasks/{incident_test_data['task1'].id}/entries",
        json={"value_numeric": 9.0, "unit": "C"},
        headers={"Authorization": f"Bearer {token_staff1}"},
    )
    entry_id = res.json()["data"]["id"]
    inc = db_session.query(Incident).filter_by(entry_id=entry_id).first()
    ca = db_session.query(CorrectiveAction).filter_by(incident_id=inc.id).first()

    # 2. Manager assigns to Staff 2
    client.post(
        f"/api/v1/corrective-actions/{ca.id}/assign",
        json={"assigned_to": str(incident_test_data["staff_a2"].id)},
        headers={"Authorization": f"Bearer {token_manager}"},
    )

    # 3. Assigned Staff 2 completes CAPA with SAFE reading (3.5 °C)
    complete_res = client.post(
        f"/api/v1/corrective-actions/{ca.id}/complete",
        json={"value_numeric": 3.5, "unit": "C", "notes": "Thermostat reset. Temperature restored to 3.5C."},
        headers={"Authorization": f"Bearer {token_staff2}"},
    )
    assert complete_res.status_code == 200
    assert complete_res.json()["data"]["status"] == "VERIFIED"
    assert complete_res.json()["data"]["recheck_entry_id"] is not None

    # Verify Incident moved to RESOLVED
    inc_res = client.get(
        f"/api/v1/incidents/{inc.id}",
        headers={"Authorization": f"Bearer {token_manager}"},
    )
    assert inc_res.json()["data"]["status"] == "RESOLVED"


def test_recheck_still_critical_rejected(incident_test_data, db_session: Session):
    token_staff1 = incident_test_data["token_staff_a1"]
    token_manager = incident_test_data["token_manager_a"]

    res = client.post(
        f"/api/v1/tasks/{incident_test_data['task1'].id}/entries",
        json={"value_numeric": 9.0, "unit": "C"},
        headers={"Authorization": f"Bearer {token_staff1}"},
    )
    entry_id = res.json()["data"]["id"]
    inc = db_session.query(Incident).filter_by(entry_id=entry_id).first()
    ca = db_session.query(CorrectiveAction).filter_by(incident_id=inc.id).first()

    # Manager assigns to Staff 1
    client.post(
        f"/api/v1/corrective-actions/{ca.id}/assign",
        json={"assigned_to": str(incident_test_data["staff_a1"].id)},
        headers={"Authorization": f"Bearer {token_manager}"},
    )

    # Staff submits ANOTHER CRITICAL reading (8.5 °C > 7.0 °C)
    complete_res = client.post(
        f"/api/v1/corrective-actions/{ca.id}/complete",
        json={"value_numeric": 8.5, "unit": "C", "notes": "Attempted thermostat fix but still hot."},
        headers={"Authorization": f"Bearer {token_staff1}"},
    )
    assert complete_res.status_code == 422
    assert complete_res.json()["error"]["code"] == "RECHECK_STILL_CRITICAL"

    # CAPA status should be REJECTED and incident INVESTIGATING
    db_session.expire_all()
    ca_db = db_session.query(CorrectiveAction).filter_by(id=ca.id).first()
    assert ca_db.status == "REJECTED"


def test_unassigned_staff_cannot_complete_assigned_capa(incident_test_data, db_session: Session):
    token_staff1 = incident_test_data["token_staff_a1"]
    token_staff2 = incident_test_data["token_staff_a2"]
    token_manager = incident_test_data["token_manager_a"]

    res = client.post(
        f"/api/v1/tasks/{incident_test_data['task1'].id}/entries",
        json={"value_numeric": 9.0, "unit": "C"},
        headers={"Authorization": f"Bearer {token_staff1}"},
    )
    entry_id = res.json()["data"]["id"]
    inc = db_session.query(Incident).filter_by(entry_id=entry_id).first()
    ca = db_session.query(CorrectiveAction).filter_by(incident_id=inc.id).first()

    # Manager assigns to Staff 1
    client.post(
        f"/api/v1/corrective-actions/{ca.id}/assign",
        json={"assigned_to": str(incident_test_data["staff_a1"].id)},
        headers={"Authorization": f"Bearer {token_manager}"},
    )

    # Unassigned Staff 2 tries to complete
    complete_res = client.post(
        f"/api/v1/corrective-actions/{ca.id}/complete",
        json={"value_numeric": 3.0, "unit": "C"},
        headers={"Authorization": f"Bearer {token_staff2}"},
    )
    assert complete_res.status_code == 403
    assert complete_res.json()["error"]["code"] == "TASK_ASSIGNMENT_DENIED"


# ------------------------------------------------------------------------------
# 6. Manager Verification & Closure Workflow
# ------------------------------------------------------------------------------

def test_manager_verification_and_incident_closure(incident_test_data, db_session: Session):
    token_staff1 = incident_test_data["token_staff_a1"]
    token_manager = incident_test_data["token_manager_a"]

    # 1. Trigger incident
    res = client.post(
        f"/api/v1/tasks/{incident_test_data['task1'].id}/entries",
        json={"value_numeric": 9.0, "unit": "C"},
        headers={"Authorization": f"Bearer {token_staff1}"},
    )
    entry_id = res.json()["data"]["id"]
    inc = db_session.query(Incident).filter_by(entry_id=entry_id).first()
    ca = db_session.query(CorrectiveAction).filter_by(incident_id=inc.id).first()

    # 2. Staff completes recheck
    client.post(
        f"/api/v1/corrective-actions/{ca.id}/complete",
        json={"value_numeric": 3.0, "unit": "C"},
        headers={"Authorization": f"Bearer {token_staff1}"},
    )

    # 3. Manager verifies & approves CAPA
    verify_res = client.post(
        f"/api/v1/corrective-actions/{ca.id}/verify",
        json={"approved": True, "notes": "Verified temperature log. Closure approved."},
        headers={"Authorization": f"Bearer {token_manager}"},
    )
    assert verify_res.status_code == 200
    ca_data = verify_res.json()["data"]
    assert ca_data["status"] == "VERIFIED"
    assert ca_data["verified_by"] == str(incident_test_data["manager_a"].id)

    # Verify Incident is CLOSED
    db_session.expire_all()
    inc_db = db_session.query(Incident).filter_by(id=inc.id).first()
    assert inc_db.status == "CLOSED"
    assert inc_db.resolved_at is not None


def test_manager_verification_rejection_reopens_capa(incident_test_data, db_session: Session):
    token_staff1 = incident_test_data["token_staff_a1"]
    token_manager = incident_test_data["token_manager_a"]

    res = client.post(
        f"/api/v1/tasks/{incident_test_data['task1'].id}/entries",
        json={"value_numeric": 9.0, "unit": "C"},
        headers={"Authorization": f"Bearer {token_staff1}"},
    )
    entry_id = res.json()["data"]["id"]
    inc = db_session.query(Incident).filter_by(entry_id=entry_id).first()
    ca = db_session.query(CorrectiveAction).filter_by(incident_id=inc.id).first()

    # Staff completes recheck
    client.post(
        f"/api/v1/corrective-actions/{ca.id}/complete",
        json={"value_numeric": 3.0, "unit": "C"},
        headers={"Authorization": f"Bearer {token_staff1}"},
    )

    # Manager rejects verification (e.g. invalid documentation)
    verify_res = client.post(
        f"/api/v1/corrective-actions/{ca.id}/verify",
        json={"approved": False, "notes": "Physical photo evidence is missing. Re-do check with evidence photo."},
        headers={"Authorization": f"Bearer {token_manager}"},
    )
    assert verify_res.status_code == 200
    assert verify_res.json()["data"]["status"] == "IN_PROGRESS"

    db_session.expire_all()
    inc_db = db_session.query(Incident).filter_by(id=inc.id).first()
    assert inc_db.status == "INVESTIGATING"


# ------------------------------------------------------------------------------
# 7. Prohibited Direct Status Mutations
# ------------------------------------------------------------------------------

def test_direct_incident_status_patch_prohibited(incident_test_data, db_session: Session):
    token_manager = incident_test_data["token_manager_a"]
    token_staff1 = incident_test_data["token_staff_a1"]

    res = client.post(
        f"/api/v1/tasks/{incident_test_data['task1'].id}/entries",
        json={"value_numeric": 9.0, "unit": "C"},
        headers={"Authorization": f"Bearer {token_staff1}"},
    )
    entry_id = res.json()["data"]["id"]
    inc = db_session.query(Incident).filter_by(entry_id=entry_id).first()

    patch_res = client.patch(
        f"/api/v1/incidents/{inc.id}",
        json={"status": "CLOSED"},
        headers={"Authorization": f"Bearer {token_manager}"},
    )
    assert patch_res.status_code == 409
    assert patch_res.json()["error"]["code"] == "DIRECT_STATUS_MUTATION_PROHIBITED"


def test_direct_corrective_action_status_patch_prohibited(incident_test_data, db_session: Session):
    token_manager = incident_test_data["token_manager_a"]
    token_staff1 = incident_test_data["token_staff_a1"]

    res = client.post(
        f"/api/v1/tasks/{incident_test_data['task1'].id}/entries",
        json={"value_numeric": 9.0, "unit": "C"},
        headers={"Authorization": f"Bearer {token_staff1}"},
    )
    entry_id = res.json()["data"]["id"]
    inc = db_session.query(Incident).filter_by(entry_id=entry_id).first()
    ca = db_session.query(CorrectiveAction).filter_by(incident_id=inc.id).first()

    patch_res = client.patch(
        f"/api/v1/corrective-actions/{ca.id}",
        json={"status": "VERIFIED"},
        headers={"Authorization": f"Bearer {token_manager}"},
    )
    assert patch_res.status_code == 409
    assert patch_res.json()["error"]["code"] == "DIRECT_STATUS_MUTATION_PROHIBITED"


# ------------------------------------------------------------------------------
# 8. Cross-Tenant Isolation & Authorization
# ------------------------------------------------------------------------------

def test_cross_tenant_incident_access_forbidden(incident_test_data, db_session: Session):
    token_staff1 = incident_test_data["token_staff_a1"]
    token_staff_b1 = incident_test_data["token_staff_b1"]

    res = client.post(
        f"/api/v1/tasks/{incident_test_data['task1'].id}/entries",
        json={"value_numeric": 9.0, "unit": "C"},
        headers={"Authorization": f"Bearer {token_staff1}"},
    )
    entry_id = res.json()["data"]["id"]
    inc = db_session.query(Incident).filter_by(entry_id=entry_id).first()

    # User from Rest B tries to access Rest A's incident
    get_res = client.get(
        f"/api/v1/incidents/{inc.id}",
        headers={"Authorization": f"Bearer {token_staff_b1}"},
    )
    assert get_res.status_code == 403
    assert get_res.json()["error"]["code"] == "FORBIDDEN_CROSS_TENANT"


def test_cross_tenant_corrective_action_complete_forbidden(incident_test_data, db_session: Session):
    token_staff1 = incident_test_data["token_staff_a1"]
    token_staff_b1 = incident_test_data["token_staff_b1"]

    res = client.post(
        f"/api/v1/tasks/{incident_test_data['task1'].id}/entries",
        json={"value_numeric": 9.0, "unit": "C"},
        headers={"Authorization": f"Bearer {token_staff1}"},
    )
    entry_id = res.json()["data"]["id"]
    inc = db_session.query(Incident).filter_by(entry_id=entry_id).first()
    ca = db_session.query(CorrectiveAction).filter_by(incident_id=inc.id).first()

    complete_res = client.post(
        f"/api/v1/corrective-actions/{ca.id}/complete",
        json={"value_numeric": 3.0, "unit": "C"},
        headers={"Authorization": f"Bearer {token_staff_b1}"},
    )
    assert complete_res.status_code == 403
    assert complete_res.json()["error"]["code"] == "FORBIDDEN_CROSS_TENANT"
