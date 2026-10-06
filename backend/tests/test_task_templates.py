import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.main import app
from app.models.identity import Restaurant, Role, User, UserRole
from app.models.tasks_and_rules import TaskCategory, TaskTemplate, TaskTemplateVersion

client = TestClient(app)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def template_test_data(db_session: Session):
    # Ensure roles exist
    staff_role = db_session.query(Role).filter_by(name="STAFF").first()
    if not staff_role:
        staff_role = Role(id=uuid.uuid4(), name="STAFF", is_system_role=True)
        db_session.add(staff_role)

    manager_role = db_session.query(Role).filter_by(name="MANAGER").first()
    if not manager_role:
        manager_role = Role(id=uuid.uuid4(), name="MANAGER", is_system_role=True)
        db_session.add(manager_role)

    db_session.commit()

    # Create Restaurant A
    rest_a = Restaurant(
        id=uuid.uuid4(),
        name="Restaurant A Kitchen",
        category="RESTAURANT",
        address_line1="Address A",
        city="Bengaluru",
        state="Karnataka",
        pincode="560001",
        status="ACTIVE",
    )
    db_session.add(rest_a)

    # Create Restaurant B
    rest_b = Restaurant(
        id=uuid.uuid4(),
        name="Restaurant B Kitchen",
        category="CLOUD_KITCHEN",
        address_line1="Address B",
        city="Mumbai",
        state="Maharashtra",
        pincode="400001",
        status="ACTIVE",
    )
    db_session.add(rest_b)
    db_session.commit()

    # Create Manager User for Restaurant A
    manager_a = User(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        name="Manager A",
        phone=f"+9196{uuid.uuid4().hex[:8]}",
        status="ACTIVE",
    )
    db_session.add(manager_a)
    db_session.add(UserRole(id=uuid.uuid4(), user_id=manager_a.id, role_id=manager_role.id, restaurant_id=rest_a.id))

    # Create Staff User for Restaurant A
    staff_a = User(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        name="Staff A",
        phone=f"+9195{uuid.uuid4().hex[:8]}",
        status="ACTIVE",
    )
    db_session.add(staff_a)
    db_session.add(UserRole(id=uuid.uuid4(), user_id=staff_a.id, role_id=staff_role.id, restaurant_id=rest_a.id))

    # Create Manager User for Restaurant B
    manager_b = User(
        id=uuid.uuid4(),
        restaurant_id=rest_b.id,
        name="Manager B",
        phone=f"+9194{uuid.uuid4().hex[:8]}",
        status="ACTIVE",
    )
    db_session.add(manager_b)
    db_session.add(UserRole(id=uuid.uuid4(), user_id=manager_b.id, role_id=manager_role.id, restaurant_id=rest_b.id))

    # Create Task Category
    category = TaskCategory(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        name="Temperature Logging",
        code="TEMP_LOG",
        is_active=True,
    )
    db_session.add(category)

    db_session.commit()

    # Generate Access Tokens
    token_mgr_a, _ = create_access_token(user_id=manager_a.id, tenant_id=rest_a.id, roles=["MANAGER"])
    token_staff_a, _ = create_access_token(user_id=staff_a.id, tenant_id=rest_a.id, roles=["STAFF"])
    token_mgr_b, _ = create_access_token(user_id=manager_b.id, tenant_id=rest_b.id, roles=["MANAGER"])

    yield {
        "rest_a": rest_a,
        "rest_b": rest_b,
        "manager_a": manager_a,
        "staff_a": staff_a,
        "manager_b": manager_b,
        "category": category,
        "token_mgr_a": token_mgr_a,
        "token_staff_a": token_staff_a,
        "token_mgr_b": token_mgr_b,
    }

    # Clean up test data
    from app.models.tasks_and_rules import Task
    db_session.query(Task).delete()
    db_session.query(TaskTemplateVersion).delete()
    db_session.query(TaskTemplate).delete()
    db_session.query(TaskCategory).filter_by(id=category.id).delete()
    db_session.query(UserRole).filter(
        UserRole.user_id.in_([manager_a.id, staff_a.id, manager_b.id])
    ).delete(synchronize_session=False)
    db_session.query(User).filter(
        User.id.in_([manager_a.id, staff_a.id, manager_b.id])
    ).delete(synchronize_session=False)
    db_session.query(Restaurant).filter(
        Restaurant.id.in_([rest_a.id, rest_b.id])
    ).delete(synchronize_session=False)
    db_session.commit()


# ------------------------------------------------------------------------------
# 1. Template Creation & Initial Version Tests
# ------------------------------------------------------------------------------

def test_create_task_template_success(template_test_data):
    token = template_test_data["token_mgr_a"]
    category_id = str(template_test_data["category"].id)

    payload = {
        "category_id": category_id,
        "name": "Chiller Temp Check",
        "code": "CHILLER_TEMP_01",
        "description": "Daily morning walk-in chiller temperature check",
        "frequency_type": "DAILY",
        "configuration_jsonb": {
            "target_unit": "C",
            "min_val": 0,
            "max_val": 4,
            "requires_evidence": True,
        },
    }

    res = client.post(
        "/api/v1/task-templates",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 201
    body = res.json()
    assert body["success"] is True
    assert body["data"]["name"] == "Chiller Temp Check"
    assert body["data"]["code"] == "CHILLER_TEMP_01"
    assert body["data"]["latest_version_number"] == 1
    assert body["data"]["latest_version"]["version_number"] == 1
    assert body["data"]["latest_version"]["configuration_jsonb"]["max_val"] == 4


def test_create_template_duplicate_code_conflict(template_test_data):
    token = template_test_data["token_mgr_a"]
    category_id = str(template_test_data["category"].id)

    payload = {
        "category_id": category_id,
        "name": "Deep Freezer Check",
        "code": "FREEZER_TEMP_01",
        "configuration_jsonb": {"min_val": -22, "max_val": -18},
    }

    res1 = client.post("/api/v1/task-templates", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert res1.status_code == 201

    # Duplicate code attempt for same outlet
    res2 = client.post("/api/v1/task-templates", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert res2.status_code == 409
    assert res2.json()["error"]["code"] == "DUPLICATE_TEMPLATE_CODE"


def test_create_template_staff_forbidden(template_test_data):
    token = template_test_data["token_staff_a"]
    category_id = str(template_test_data["category"].id)

    payload = {
        "category_id": category_id,
        "name": "Staff Created Template",
        "code": "STAFF_CODE",
        "configuration_jsonb": {"min_val": 0},
    }

    res = client.post("/api/v1/task-templates", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"


# ------------------------------------------------------------------------------
# 2. Immutable Versioning & Update Tests
# ------------------------------------------------------------------------------

def test_immutable_version_increment_on_update(template_test_data, db_session: Session):
    token = template_test_data["token_mgr_a"]
    category_id = str(template_test_data["category"].id)

    # Step 1: Create initial template (Version 1)
    create_payload = {
        "category_id": category_id,
        "name": "Hygiene Checklist",
        "code": "HYGIENE_CHECK",
        "configuration_jsonb": {"items": ["Sanitize Tables", "Clean Prep Surface"]},
    }
    create_res = client.post("/api/v1/task-templates", json=create_payload, headers={"Authorization": f"Bearer {token}"})
    assert create_res.status_code == 201
    template_id = create_res.json()["data"]["id"]

    # Step 2: Update configuration (Triggers Version 2 creation)
    update_payload = {
        "configuration_jsonb": {"items": ["Sanitize Tables", "Clean Prep Surface", "Check Handwash Station"]},
    }
    update_res = client.put(
        f"/api/v1/task-templates/{template_id}",
        json=update_payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert update_res.status_code == 200
    update_body = update_res.json()
    assert update_body["data"]["latest_version_number"] == 2
    assert update_body["data"]["latest_version"]["version_number"] == 2

    # Step 3: IMMUTABILITY VERIFICATION: Verify Version 1 remains unchanged in DB
    v1_res = client.get(
        f"/api/v1/task-templates/{template_id}/versions/1",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert v1_res.status_code == 200
    v1_data = v1_res.json()["data"]
    assert v1_data["version_number"] == 1
    assert len(v1_data["configuration_jsonb"]["items"]) == 2  # Original 2 items unchanged!

    # Verify Version 2 has 3 items
    v2_res = client.get(
        f"/api/v1/task-templates/{template_id}/versions/2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert v2_res.status_code == 200
    v2_data = v2_res.json()["data"]
    assert v2_data["version_number"] == 2
    assert len(v2_data["configuration_jsonb"]["items"]) == 3


def test_explicit_create_version_endpoint(template_test_data):
    token = template_test_data["token_mgr_a"]
    category_id = str(template_test_data["category"].id)

    create_payload = {
        "category_id": category_id,
        "name": "Oil Quality Test",
        "code": "OIL_TEST",
        "configuration_jsonb": {"max_tpm": 25},
    }
    create_res = client.post("/api/v1/task-templates", json=create_payload, headers={"Authorization": f"Bearer {token}"})
    template_id = create_res.json()["data"]["id"]

    # Call explicit POST /versions endpoint
    version_res = client.post(
        f"/api/v1/task-templates/{template_id}/versions",
        json={"configuration_jsonb": {"max_tpm": 24, "check_color": True}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert version_res.status_code == 201
    v_body = version_res.json()
    assert v_body["data"]["version_number"] == 2
    assert v_body["data"]["configuration_jsonb"]["max_tpm"] == 24


# ------------------------------------------------------------------------------
# 3. Tenant Isolation & Retrieval Tests
# ------------------------------------------------------------------------------

def test_tenant_isolation_cross_tenant_access_denied(template_test_data):
    token_mgr_a = template_test_data["token_mgr_a"]
    token_mgr_b = template_test_data["token_mgr_b"]
    category_id = str(template_test_data["category"].id)

    # Manager A creates template in Restaurant A
    create_res = client.post(
        "/api/v1/task-templates",
        json={
            "category_id": category_id,
            "name": "Rest A Private Template",
            "code": "PRIVATE_A",
            "configuration_jsonb": {"val": 1},
        },
        headers={"Authorization": f"Bearer {token_mgr_a}"},
    )
    template_id = create_res.json()["data"]["id"]

    # Manager B (from Restaurant B) attempts GET -> FORBIDDEN (403)
    get_res = client.get(
        f"/api/v1/task-templates/{template_id}",
        headers={"Authorization": f"Bearer {token_mgr_b}"},
    )
    assert get_res.status_code == 403
    assert get_res.json()["error"]["code"] == "FORBIDDEN_CROSS_TENANT"

    # Manager B attempts PUT -> FORBIDDEN (403)
    put_res = client.put(
        f"/api/v1/task-templates/{template_id}",
        json={"name": "Hacked Name"},
        headers={"Authorization": f"Bearer {token_mgr_b}"},
    )
    assert put_res.status_code == 403


def test_list_templates_returns_tenant_scoped_records(template_test_data):
    token_mgr_a = template_test_data["token_mgr_a"]
    category_id = str(template_test_data["category"].id)

    client.post(
        "/api/v1/task-templates",
        json={
            "category_id": category_id,
            "name": "Outlet Task 1",
            "code": "TASK_01",
            "configuration_jsonb": {"rule": "A"},
        },
        headers={"Authorization": f"Bearer {token_mgr_a}"},
    )

    list_res = client.get("/api/v1/task-templates", headers={"Authorization": f"Bearer {token_mgr_a}"})
    assert list_res.status_code == 200
    body = list_res.json()

    assert body["success"] is True
    assert isinstance(body["data"], list)
    assert len(body["data"]) >= 1
    assert body["data"][0]["restaurant_id"] == str(template_test_data["rest_a"].id)
