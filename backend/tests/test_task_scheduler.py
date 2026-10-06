import uuid
from datetime import date, datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.jobs.generate_tasks import generate_tasks_for_restaurant
from app.main import app
from app.models.identity import Restaurant, Role, User, UserRole
from app.models.tasks_and_rules import Task, TaskCategory, TaskTemplate, TaskTemplateVersion

client = TestClient(app)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def scheduler_test_data(db_session: Session):
    staff_role = db_session.query(Role).filter_by(name="STAFF").first()
    if not staff_role:
        staff_role = Role(id=uuid.uuid4(), name="STAFF", is_system_role=True)
        db_session.add(staff_role)

    manager_role = db_session.query(Role).filter_by(name="MANAGER").first()
    if not manager_role:
        manager_role = Role(id=uuid.uuid4(), name="MANAGER", is_system_role=True)
        db_session.add(manager_role)

    db_session.commit()

    rest_a = Restaurant(
        id=uuid.uuid4(),
        name=f"Restaurant A {uuid.uuid4().hex[:4]}",
        category="RESTAURANT",
        address_line1="Address A",
        city="Bengaluru",
        state="Karnataka",
        pincode="560001",
        status="ACTIVE",
    )
    db_session.add(rest_a)

    rest_b = Restaurant(
        id=uuid.uuid4(),
        name=f"Restaurant B {uuid.uuid4().hex[:4]}",
        category="CLOUD_KITCHEN",
        address_line1="Address B",
        city="Mumbai",
        state="Maharashtra",
        pincode="400001",
        status="ACTIVE",
    )
    db_session.add(rest_b)
    db_session.commit()

    mgr_a = User(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        phone=f"+9198{uuid.uuid4().hex[:8]}",
        name="Manager A",
        pin_hash="hashed_pin",
        status="ACTIVE",
    )
    db_session.add(mgr_a)

    staff_a = User(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        phone=f"+9197{uuid.uuid4().hex[:8]}",
        name="Staff A",
        pin_hash="hashed_pin",
        status="ACTIVE",
    )
    db_session.add(staff_a)
    db_session.commit()

    db_session.add(UserRole(id=uuid.uuid4(), user_id=mgr_a.id, role_id=manager_role.id, restaurant_id=rest_a.id))
    db_session.add(UserRole(id=uuid.uuid4(), user_id=staff_a.id, role_id=staff_role.id, restaurant_id=rest_a.id))
    db_session.commit()

    category = TaskCategory(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        name="Temperature Checks",
        code=f"TEMP_{uuid.uuid4().hex[:4]}",
        is_active=True,
    )
    db_session.add(category)
    db_session.commit()

    mgr_a_token, _ = create_access_token(user_id=mgr_a.id, tenant_id=rest_a.id, roles=["MANAGER"])
    staff_a_token, _ = create_access_token(user_id=staff_a.id, tenant_id=rest_a.id, roles=["STAFF"])

    yield {
        "rest_a": rest_a,
        "rest_b": rest_b,
        "mgr_a": mgr_a,
        "staff_a": staff_a,
        "category": category,
        "mgr_a_token": mgr_a_token,
        "staff_a_token": staff_a_token,
    }

    # Clean up test data
    db_session.query(Task).delete()
    db_session.query(TaskTemplateVersion).delete()
    db_session.query(TaskTemplate).delete()
    db_session.query(TaskCategory).filter_by(id=category.id).delete()
    db_session.query(UserRole).filter(UserRole.user_id.in_([mgr_a.id, staff_a.id])).delete(synchronize_session=False)
    db_session.query(User).filter(User.id.in_([mgr_a.id, staff_a.id])).delete(synchronize_session=False)
    db_session.query(Restaurant).filter(Restaurant.id.in_([rest_a.id, rest_b.id])).delete(synchronize_session=False)
    db_session.commit()


def test_generate_tasks_basic(db_session: Session, scheduler_test_data):
    data = scheduler_test_data
    rest_a = data["rest_a"]
    category = data["category"]

    tmpl = TaskTemplate(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        category_id=category.id,
        name="Morning Chiller Check",
        code=f"CHILLER_AM_{uuid.uuid4().hex[:4]}",
        frequency_type="DAILY",
        is_active=True,
    )
    db_session.add(tmpl)
    db_session.commit()

    ver = TaskTemplateVersion(
        id=uuid.uuid4(),
        template_id=tmpl.id,
        version_number=1,
        configuration_jsonb={"due_time": "10:00", "min_temp": 2.0, "max_temp": 8.0},
    )
    db_session.add(ver)
    db_session.commit()

    target_d = date(2026, 10, 5)
    res = generate_tasks_for_restaurant(db_session, rest_a.id, target_d)

    assert res.templates_processed == 1
    assert res.tasks_created == 1
    assert res.tasks_skipped_existing == 0
    assert len(res.task_ids) == 1

    task = db_session.query(Task).filter_by(id=res.task_ids[0]).first()
    assert task is not None
    assert task.restaurant_id == rest_a.id
    assert task.template_id == tmpl.id
    assert task.template_version_id == ver.id
    assert task.occurrence_key == "2026-10-05"
    assert task.status == "PENDING"
    assert task.due_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M") == "2026-10-05 10:00"


def test_task_occurrence_idempotency(db_session: Session, scheduler_test_data):
    data = scheduler_test_data
    rest_a = data["rest_a"]
    category = data["category"]

    tmpl = TaskTemplate(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        category_id=category.id,
        name="Hot Holding Temp",
        code=f"HOT_HOLDING_{uuid.uuid4().hex[:4]}",
        frequency_type="DAILY",
        is_active=True,
    )
    db_session.add(tmpl)
    db_session.commit()

    ver = TaskTemplateVersion(
        id=uuid.uuid4(),
        template_id=tmpl.id,
        version_number=1,
        configuration_jsonb={"min_temp": 60.0},
    )
    db_session.add(ver)
    db_session.commit()

    target_d = date(2026, 10, 5)

    # First run
    res1 = generate_tasks_for_restaurant(db_session, rest_a.id, target_d)
    assert res1.tasks_created == 1
    assert res1.tasks_skipped_existing == 0

    # Second run (IDEMPOTENCE CHECK)
    res2 = generate_tasks_for_restaurant(db_session, rest_a.id, target_d)
    assert res2.tasks_created == 0
    assert res2.tasks_skipped_existing == 1
    assert res2.task_ids == res1.task_ids

    task_count = db_session.query(Task).filter_by(template_id=tmpl.id).count()
    assert task_count == 1


def test_different_dates_generate_separate_occurrences(db_session: Session, scheduler_test_data):
    data = scheduler_test_data
    rest_a = data["rest_a"]
    category = data["category"]

    tmpl = TaskTemplate(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        category_id=category.id,
        name="Deep Cleaning",
        code=f"DEEP_CLEAN_{uuid.uuid4().hex[:4]}",
        frequency_type="DAILY",
        is_active=True,
    )
    db_session.add(tmpl)

    ver = TaskTemplateVersion(
        id=uuid.uuid4(),
        template_id=tmpl.id,
        version_number=1,
        configuration_jsonb={},
    )
    db_session.add(ver)
    db_session.commit()

    res_oct5 = generate_tasks_for_restaurant(db_session, rest_a.id, date(2026, 10, 5))
    res_oct6 = generate_tasks_for_restaurant(db_session, rest_a.id, date(2026, 10, 6))

    assert res_oct5.tasks_created == 1
    assert res_oct6.tasks_created == 1

    task5 = db_session.query(Task).filter_by(id=res_oct5.task_ids[0]).first()
    task6 = db_session.query(Task).filter_by(id=res_oct6.task_ids[0]).first()

    assert task5.occurrence_key == "2026-10-05"
    assert task6.occurrence_key == "2026-10-06"
    assert task5.id != task6.id


def test_frequency_types_occurrence_keys(db_session: Session, scheduler_test_data):
    data = scheduler_test_data
    rest_a = data["rest_a"]
    category = data["category"]

    tmpl_shift = TaskTemplate(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        category_id=category.id,
        name="Morning Opening Shift",
        code=f"SHIFT_AM_{uuid.uuid4().hex[:4]}",
        frequency_type="SHIFT_START",
        is_active=True,
    )
    db_session.add(tmpl_shift)

    ver_shift = TaskTemplateVersion(
        id=uuid.uuid4(),
        template_id=tmpl_shift.id,
        version_number=1,
        configuration_jsonb={"shift_name": "MORNING"},
    )
    db_session.add(ver_shift)

    tmpl_monthly = TaskTemplate(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        category_id=category.id,
        name="Monthly Deep Inspection",
        code=f"MONTHLY_{uuid.uuid4().hex[:4]}",
        frequency_type="MONTHLY",
        is_active=True,
    )
    db_session.add(tmpl_monthly)

    ver_monthly = TaskTemplateVersion(
        id=uuid.uuid4(),
        template_id=tmpl_monthly.id,
        version_number=1,
        configuration_jsonb={},
    )
    db_session.add(ver_monthly)
    db_session.commit()

    res = generate_tasks_for_restaurant(db_session, rest_a.id, date(2026, 10, 5))
    assert res.tasks_created == 2

    task_shift = db_session.query(Task).filter_by(template_id=tmpl_shift.id).first()
    task_monthly = db_session.query(Task).filter_by(template_id=tmpl_monthly.id).first()

    assert task_shift.occurrence_key == "2026-10-05:MORNING"
    assert task_monthly.occurrence_key == "2026-10"


def test_tenant_isolation_in_scheduler(db_session: Session, scheduler_test_data):
    data = scheduler_test_data
    rest_a = data["rest_a"]
    rest_b = data["rest_b"]
    category = data["category"]

    tmpl_a = TaskTemplate(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        category_id=category.id,
        name="Rest A Task",
        code=f"REST_A_{uuid.uuid4().hex[:4]}",
        frequency_type="DAILY",
        is_active=True,
    )
    db_session.add(tmpl_a)

    ver_a = TaskTemplateVersion(
        id=uuid.uuid4(),
        template_id=tmpl_a.id,
        version_number=1,
        configuration_jsonb={},
    )
    db_session.add(ver_a)
    db_session.commit()

    res_b = generate_tasks_for_restaurant(db_session, rest_b.id, date(2026, 10, 5))
    assert res_b.templates_processed == 0
    assert res_b.tasks_created == 0

    res_a = generate_tasks_for_restaurant(db_session, rest_a.id, date(2026, 10, 5))
    assert res_a.templates_processed == 1
    assert res_a.tasks_created == 1


def test_api_generate_and_list_tasks(db_session: Session, scheduler_test_data):
    data = scheduler_test_data
    mgr_token = data["mgr_a_token"]
    staff_token = data["staff_a_token"]
    rest_a = data["rest_a"]
    category = data["category"]

    # Seed an active task template + version for Rest A
    tmpl = TaskTemplate(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        category_id=category.id,
        name="API Test Task",
        code=f"API_TASK_{uuid.uuid4().hex[:4]}",
        frequency_type="DAILY",
        is_active=True,
    )
    db_session.add(tmpl)
    ver = TaskTemplateVersion(
        id=uuid.uuid4(),
        template_id=tmpl.id,
        version_number=1,
        configuration_jsonb={},
    )
    db_session.add(ver)
    db_session.commit()

    # Trigger generation via API
    headers_mgr = {"Authorization": f"Bearer {mgr_token}"}
    response = client.post(
        "/api/v1/tasks/generate",
        json={"target_date": "2026-10-05"},
        headers=headers_mgr,
    )
    assert response.status_code == 201
    res_json = response.json()
    assert res_json["success"] is True
    assert res_json["data"]["tasks_created"] >= 1

    # List tasks via API
    headers_staff = {"Authorization": f"Bearer {staff_token}"}
    list_resp = client.get("/api/v1/tasks?status=PENDING", headers=headers_staff)
    assert list_resp.status_code == 200
    list_json = list_resp.json()
    assert list_json["success"] is True
    assert list_json["meta"]["pagination"]["total"] >= 1


def test_inactive_template_skipped(db_session: Session, scheduler_test_data):
    data = scheduler_test_data
    rest_a = data["rest_a"]
    category = data["category"]

    tmpl_inactive = TaskTemplate(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        category_id=category.id,
        name="Inactive Task",
        code=f"INACTIVE_{uuid.uuid4().hex[:4]}",
        frequency_type="DAILY",
        is_active=False,
    )
    db_session.add(tmpl_inactive)

    ver = TaskTemplateVersion(
        id=uuid.uuid4(),
        template_id=tmpl_inactive.id,
        version_number=1,
        configuration_jsonb={},
    )
    db_session.add(ver)
    db_session.commit()

    res = generate_tasks_for_restaurant(db_session, rest_a.id, date(2026, 10, 5))
    assert res.templates_processed == 0
    assert res.tasks_created == 0
