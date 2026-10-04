import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.main import app
from app.models.identity import Restaurant, Role, User, UserRole
from app.models.tasks_and_rules import Equipment

client = TestClient(app)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def equipment_test_data(db_session: Session):
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

    # Create Manager for Restaurant A
    manager_a = User(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        name="Manager A",
        phone="9777777771",
        status="ACTIVE",
    )
    db_session.add(manager_a)
    db_session.add(UserRole(id=uuid.uuid4(), user_id=manager_a.id, role_id=manager_role.id, restaurant_id=rest_a.id))

    # Create Staff for Restaurant A
    staff_a = User(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        name="Staff A",
        phone="9777777772",
        status="ACTIVE",
    )
    db_session.add(staff_a)
    db_session.add(UserRole(id=uuid.uuid4(), user_id=staff_a.id, role_id=staff_role.id, restaurant_id=rest_a.id))

    # Create Manager for Restaurant B
    manager_b = User(
        id=uuid.uuid4(),
        restaurant_id=rest_b.id,
        name="Manager B",
        phone="9777777773",
        status="ACTIVE",
    )
    db_session.add(manager_b)
    db_session.add(UserRole(id=uuid.uuid4(), user_id=manager_b.id, role_id=manager_role.id, restaurant_id=rest_b.id))

    db_session.commit()

    token_mgr_a, _ = create_access_token(user_id=manager_a.id, tenant_id=rest_a.id, roles=["MANAGER"])
    token_staff_a, _ = create_access_token(user_id=staff_a.id, tenant_id=rest_a.id, roles=["STAFF"])
    token_mgr_b, _ = create_access_token(user_id=manager_b.id, tenant_id=rest_b.id, roles=["MANAGER"])

    yield {
        "rest_a": rest_a,
        "rest_b": rest_b,
        "manager_a": manager_a,
        "staff_a": staff_a,
        "manager_b": manager_b,
        "token_mgr_a": token_mgr_a,
        "token_staff_a": token_staff_a,
        "token_mgr_b": token_mgr_b,
    }

    # Clean up test data
    db_session.query(Equipment).delete()
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
# 1. Equipment Creation & Validation Tests
# ------------------------------------------------------------------------------

def test_create_equipment_success(equipment_test_data):
    token = equipment_test_data["token_mgr_a"]

    payload = {
        "name": "Walk-In Chiller #1",
        "equipment_type": "CHILLER",
        "location": "Main Kitchen Area",
        "serial_number": "SN-CHILLER-2026-01",
        "min_temp": 0.0,
        "max_temp": 4.0,
        "status": "OPERATIONAL",
    }

    res = client.post("/api/v1/equipment", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 201
    body = res.json()

    assert body["success"] is True
    assert body["data"]["name"] == "Walk-In Chiller #1"
    assert body["data"]["equipment_type"] == "CHILLER"
    assert body["data"]["min_temp"] == 0.0
    assert body["data"]["max_temp"] == 4.0
    assert body["data"]["status"] == "OPERATIONAL"
    assert body["data"]["restaurant_id"] == str(equipment_test_data["rest_a"].id)


def test_create_equipment_invalid_temperature_range(equipment_test_data):
    token = equipment_test_data["token_mgr_a"]

    # min_temp > max_temp should fail validation (422)
    payload = {
        "name": "Broken Chiller",
        "equipment_type": "CHILLER",
        "min_temp": 10.0,
        "max_temp": 2.0,
    }

    res = client.post("/api/v1/equipment", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 422
    body = res.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_create_equipment_invalid_status(equipment_test_data):
    token = equipment_test_data["token_mgr_a"]

    payload = {
        "name": "Deep Freezer #2",
        "equipment_type": "FREEZER",
        "status": "INVALID_STATUS_CODE",
    }

    res = client.post("/api/v1/equipment", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 422


def test_create_equipment_staff_forbidden(equipment_test_data):
    token = equipment_test_data["token_staff_a"]

    payload = {
        "name": "Staff Added Equipment",
        "equipment_type": "DISHWASHER",
    }

    res = client.post("/api/v1/equipment", json=payload, headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"


# ------------------------------------------------------------------------------
# 2. Equipment CRUD & Update Tests
# ------------------------------------------------------------------------------

def test_update_equipment_success_and_status_change(equipment_test_data):
    token = equipment_test_data["token_mgr_a"]

    # Step 1: Create Equipment
    create_res = client.post(
        "/api/v1/equipment",
        json={"name": "Hot Holding Oven", "equipment_type": "OVEN", "min_temp": 60.0, "max_temp": 90.0},
        headers={"Authorization": f"Bearer {token}"},
    )
    eq_id = create_res.json()["data"]["id"]

    # Step 2: Update status to MAINTENANCE and update location
    update_res = client.put(
        f"/api/v1/equipment/{eq_id}",
        json={"status": "MAINTENANCE", "location": "Service Line 1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert update_res.status_code == 200
    update_body = update_res.json()

    assert update_body["success"] is True
    assert update_body["data"]["status"] == "MAINTENANCE"
    assert update_body["data"]["location"] == "Service Line 1"


def test_delete_equipment_success(equipment_test_data):
    token = equipment_test_data["token_mgr_a"]

    create_res = client.post(
        "/api/v1/equipment",
        json={"name": "Temporary Blender", "equipment_type": "MIXER"},
        headers={"Authorization": f"Bearer {token}"},
    )
    eq_id = create_res.json()["data"]["id"]

    del_res = client.delete(f"/api/v1/equipment/{eq_id}", headers={"Authorization": f"Bearer {token}"})
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True

    # Verify GET returns 404
    get_res = client.get(f"/api/v1/equipment/{eq_id}", headers={"Authorization": f"Bearer {token}"})
    assert get_res.status_code == 404


# ------------------------------------------------------------------------------
# 3. Tenant Isolation & Search Filtering Tests
# ------------------------------------------------------------------------------

def test_tenant_isolation_cross_tenant_equipment_access(equipment_test_data):
    token_mgr_a = equipment_test_data["token_mgr_a"]
    token_mgr_b = equipment_test_data["token_mgr_b"]

    create_res = client.post(
        "/api/v1/equipment",
        json={"name": "Rest A Deep Freezer", "equipment_type": "FREEZER"},
        headers={"Authorization": f"Bearer {token_mgr_a}"},
    )
    eq_id = create_res.json()["data"]["id"]

    # Manager B attempts GET -> FORBIDDEN (403)
    get_res = client.get(f"/api/v1/equipment/{eq_id}", headers={"Authorization": f"Bearer {token_mgr_b}"})
    assert get_res.status_code == 403
    assert get_res.json()["error"]["code"] == "FORBIDDEN_CROSS_TENANT"

    # Manager B attempts PUT -> FORBIDDEN (403)
    put_res = client.put(
        f"/api/v1/equipment/{eq_id}",
        json={"name": "Hacked Equipment Name"},
        headers={"Authorization": f"Bearer {token_mgr_b}"},
    )
    assert put_res.status_code == 403


def test_list_equipment_filtering_and_search(equipment_test_data):
    token = equipment_test_data["token_mgr_a"]

    client.post(
        "/api/v1/equipment",
        json={"name": "Display Chiller Alpha", "equipment_type": "CHILLER", "status": "OPERATIONAL"},
        headers={"Authorization": f"Bearer {token}"},
    )
    client.post(
        "/api/v1/equipment",
        json={"name": "Blast Freezer Beta", "equipment_type": "FREEZER", "status": "MAINTENANCE"},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Filter by equipment_type=FREEZER
    res_freezer = client.get("/api/v1/equipment?equipment_type=FREEZER", headers={"Authorization": f"Bearer {token}"})
    assert res_freezer.status_code == 200
    data_freezer = res_freezer.json()["data"]
    assert all(eq["equipment_type"] == "FREEZER" for eq in data_freezer)

    # Search by name "Alpha"
    res_search = client.get("/api/v1/equipment?search=Alpha", headers={"Authorization": f"Bearer {token}"})
    assert res_search.status_code == 200
    data_search = res_search.json()["data"]
    assert len(data_search) == 1
    assert "Alpha" in data_search[0]["name"]
