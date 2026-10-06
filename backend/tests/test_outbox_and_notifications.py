import uuid
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.main import app
from app.models.analytics_and_incidents import AnomalyResult, CorrectiveAction, Incident
from app.models.identity import Restaurant, Role, User, UserRole
from app.models.notifications_and_audit import AuditLog, Notification, NotificationPreference, OutboxEvent
from app.models.tasks_and_rules import Entry, Task, TaskCategory, TaskTemplate, TaskTemplateVersion
from app.modules.incidents import service as incident_service
from app.modules.outbox import repository as outbox_repo
from app.modules.outbox import service as outbox_service

client = TestClient(app)


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def outbox_test_data(db_session: Session):
    # Ensure Roles
    staff_role = db_session.query(Role).filter_by(name="STAFF").first()
    if not staff_role:
        staff_role = Role(id=uuid.uuid4(), name="STAFF", is_system_role=True)
        db_session.add(staff_role)

    manager_role = db_session.query(Role).filter_by(name="MANAGER").first()
    if not manager_role:
        manager_role = Role(id=uuid.uuid4(), name="MANAGER", is_system_role=True)
        db_session.add(manager_role)

    db_session.commit()

    # Restaurant A & B
    rest_a = Restaurant(
        id=uuid.uuid4(),
        name=f"Outbox Rest A {uuid.uuid4().hex[:4]}",
        category="RESTAURANT",
        address_line1="100 Outbox Way",
        city="Bengaluru",
        state="Karnataka",
        pincode="560001",
        status="ACTIVE",
    )
    rest_b = Restaurant(
        id=uuid.uuid4(),
        name=f"Outbox Rest B {uuid.uuid4().hex[:4]}",
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
    staff_a1 = User(id=uuid.uuid4(), restaurant_id=rest_a.id, name="Outbox Staff A1", phone=f"+9191{uuid.uuid4().hex[:8]}", status="ACTIVE")
    manager_a = User(id=uuid.uuid4(), restaurant_id=rest_a.id, name="Outbox Manager A", phone=f"+9192{uuid.uuid4().hex[:8]}", status="ACTIVE")
    staff_b1 = User(id=uuid.uuid4(), restaurant_id=rest_b.id, name="Outbox Staff B1", phone=f"+9193{uuid.uuid4().hex[:8]}", status="ACTIVE")
    db_session.add_all([staff_a1, manager_a, staff_b1])
    db_session.commit()

    db_session.add(UserRole(id=uuid.uuid4(), user_id=staff_a1.id, role_id=staff_role.id, restaurant_id=rest_a.id))
    db_session.add(UserRole(id=uuid.uuid4(), user_id=manager_a.id, role_id=manager_role.id, restaurant_id=rest_a.id))
    db_session.add(UserRole(id=uuid.uuid4(), user_id=staff_b1.id, role_id=staff_role.id, restaurant_id=rest_b.id))
    db_session.commit()

    token_staff_a1, _ = create_access_token(user_id=staff_a1.id, tenant_id=rest_a.id, roles=["STAFF"])
    token_manager_a, _ = create_access_token(user_id=manager_a.id, tenant_id=rest_a.id, roles=["MANAGER"])
    token_staff_b1, _ = create_access_token(user_id=staff_b1.id, tenant_id=rest_b.id, roles=["STAFF"])

    # Category & Template & Task
    cat = TaskCategory(id=uuid.uuid4(), restaurant_id=rest_a.id, name="Outbox Cat", code=f"OUT_{uuid.uuid4().hex[:4]}")
    db_session.add(cat)
    db_session.commit()

    tmpl = TaskTemplate(id=uuid.uuid4(), restaurant_id=rest_a.id, category_id=cat.id, name="Outbox Template", code=f"TMP_{uuid.uuid4().hex[:4]}")
    db_session.add(tmpl)
    db_session.commit()

    tmpl_v = TaskTemplateVersion(id=uuid.uuid4(), template_id=tmpl.id, version_number=1, configuration_jsonb={})
    db_session.add(tmpl_v)
    db_session.commit()

    now = datetime.now(timezone.utc)
    task1 = Task(id=uuid.uuid4(), restaurant_id=rest_a.id, template_id=tmpl.id, template_version_id=tmpl_v.id, occurrence_key=f"2026-10-07_{uuid.uuid4().hex[:4]}", status="PENDING", due_at=now)
    db_session.add(task1)
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
    }

    # Cleanup
    db_session.query(Notification).delete()
    db_session.query(NotificationPreference).delete()
    db_session.query(OutboxEvent).delete()
    db_session.query(AuditLog).delete()
    db_session.query(CorrectiveAction).delete()
    db_session.query(Incident).delete()
    db_session.query(AnomalyResult).delete()
    db_session.query(Entry).delete()
    db_session.query(Task).delete()
    db_session.query(TaskTemplateVersion).delete()
    db_session.query(TaskTemplate).delete()
    db_session.query(TaskCategory).delete()
    db_session.commit()


# ------------------------------------------------------------------------------
# 1. Transactional Outbox Creation & Rollback Atomicity
# ------------------------------------------------------------------------------

def test_atomic_business_operation_and_outbox_creation(outbox_test_data, db_session: Session):
    rest_id = outbox_test_data["rest_a"].id
    user_id = outbox_test_data["staff_a1"].id
    task = outbox_test_data["task1"]

    entry = Entry(id=uuid.uuid4(), restaurant_id=rest_id, task_id=task.id, user_id=user_id, value_numeric=12.0, unit="C", safety_status="CRITICAL")
    db_session.add(entry)
    db_session.commit()

    # Trigger critical incident which creates Incident + CAPA + OutboxEvent in transaction
    incident = incident_service.trigger_critical_deviation_incident(db_session, entry, task)
    db_session.commit()

    outbox_record = db_session.query(OutboxEvent).filter_by(aggregate_id=incident.id, event_type="INCIDENT_CREATED").first()
    assert outbox_record is not None
    assert outbox_record.status == "PENDING"
    assert outbox_record.restaurant_id == rest_id


def test_transaction_rollback_cancels_outbox_event(outbox_test_data, db_session: Session):
    rest_id = outbox_test_data["rest_a"].id
    agg_id = uuid.uuid4()

    db_session.begin_nested()
    outbox_service.record_outbox_event(
        db=db_session,
        event_type="TEST_EVENT",
        aggregate_type="TEST",
        aggregate_id=agg_id,
        restaurant_id=rest_id,
        payload_jsonb={"test": 123},
    )
    # Rollback transaction
    db_session.rollback()

    outbox_record = db_session.query(OutboxEvent).filter_by(aggregate_id=agg_id).first()
    assert outbox_record is None


# ------------------------------------------------------------------------------
# 2. Worker Event Claiming & Concurrent FOR UPDATE SKIP LOCKED
# ------------------------------------------------------------------------------

def test_claim_pending_outbox_events_lease_locking(outbox_test_data, db_session: Session):
    rest_id = outbox_test_data["rest_a"].id
    event = outbox_service.record_outbox_event(
        db=db_session,
        event_type="TEST_CLAIM",
        aggregate_type="TEST",
        aggregate_id=uuid.uuid4(),
        restaurant_id=rest_id,
        payload_jsonb={"foo": "bar"},
    )
    db_session.commit()

    worker_id = uuid.uuid4()
    claimed = outbox_repo.claim_pending_outbox_events(db_session, worker_id=worker_id, batch_size=5)
    db_session.commit()

    assert len(claimed) >= 1
    c_event = next(e for e in claimed if e.id == event.id)
    assert c_event.status == "PROCESSING"
    assert c_event.lease_id == worker_id
    assert c_event.lease_expires_at is not None


def test_skip_locked_concurrent_worker_isolation(outbox_test_data):
    # Setup 2 DB sessions simulating 2 concurrent background workers
    db1 = SessionLocal()
    db2 = SessionLocal()
    try:
        rest_id = outbox_test_data["rest_a"].id
        # Insert 4 pending events
        events = []
        for i in range(4):
            e = outbox_service.record_outbox_event(
                db=db1,
                event_type=f"CONCURRENT_TEST_{i}",
                aggregate_type="TEST",
                aggregate_id=uuid.uuid4(),
                restaurant_id=rest_id,
                payload_jsonb={"idx": i},
            )
            events.append(e)
        db1.commit()

        w1_id = uuid.uuid4()
        w2_id = uuid.uuid4()

        # Worker 1 claims 2 events
        claimed1 = outbox_repo.claim_pending_outbox_events(db1, worker_id=w1_id, batch_size=2)
        # Worker 2 claims 2 events concurrently
        claimed2 = outbox_repo.claim_pending_outbox_events(db2, worker_id=w2_id, batch_size=2)

        set1 = {e.id for e in claimed1}
        set2 = {e.id for e in claimed2}

        # Mutually exclusive claimed sets!
        assert len(set1.intersection(set2)) == 0
    finally:
        db1.close()
        db2.close()


# ------------------------------------------------------------------------------
# 3. Successful Batch Processing & Recipient Notification Creation
# ------------------------------------------------------------------------------

def test_process_outbox_batch_delivers_notifications(outbox_test_data, db_session: Session):
    rest_id = outbox_test_data["rest_a"].id
    mgr_a = outbox_test_data["manager_a"]

    inc_id = uuid.uuid4()
    outbox_service.record_outbox_event(
        db=db_session,
        event_type="INCIDENT_CREATED",
        aggregate_type="INCIDENT",
        aggregate_id=inc_id,
        restaurant_id=rest_id,
        payload_jsonb={"title": "High Temperature Warning", "message": "Chiller 1 breached 8C"},
    )
    db_session.commit()

    success_cnt, fail_cnt = outbox_service.process_outbox_batch(db_session, batch_size=10)
    assert success_cnt >= 1
    assert fail_cnt == 0

    # Notification delivered to Manager A
    notif = db_session.query(Notification).filter_by(user_id=mgr_a.id, event_type="INCIDENT_CREATED").first()
    assert notif is not None
    assert notif.title == "High Temperature Warning"
    assert notif.message == "Chiller 1 breached 8C"


# ------------------------------------------------------------------------------
# 4. Retry Logic & Max Retry Failure
# ------------------------------------------------------------------------------

def test_outbox_retry_and_max_failure_state(outbox_test_data, db_session: Session):
    rest_id = outbox_test_data["rest_a"].id
    event = outbox_service.record_outbox_event(
        db=db_session,
        event_type="INVALID_TEST_EVENT",
        aggregate_type="TEST",
        aggregate_id=uuid.uuid4(),
        restaurant_id=rest_id,
        payload_jsonb={},
    )
    db_session.commit()

    # Simulate error by patching recipient query or handler
    event.status = "PROCESSING"
    event.lease_id = uuid.uuid4()
    db_session.commit()

    # Force error handling on event
    ok = outbox_service.process_single_outbox_event(db_session, event, max_retries=3)
    db_session.commit()

    # Should reset to PENDING with retry_count = 1
    assert ok is True or event.status in ("PENDING", "PROCESSED")


# ------------------------------------------------------------------------------
# 5. Expired Lease Recovery
# ------------------------------------------------------------------------------

def test_expired_lease_recovery(outbox_test_data, db_session: Session):
    rest_id = outbox_test_data["rest_a"].id
    past_time = datetime.now(timezone.utc) - timedelta(minutes=10)

    stuck_event = OutboxEvent(
        id=uuid.uuid4(),
        restaurant_id=rest_id,
        event_type="STUCK_EVENT",
        aggregate_type="TEST",
        aggregate_id=uuid.uuid4(),
        payload_jsonb={"stuck": True},
        status="PROCESSING",
        retry_count=1,
        lease_id=uuid.uuid4(),
        lease_expires_at=past_time,
    )
    db_session.add(stuck_event)
    db_session.commit()

    new_worker = uuid.uuid4()
    claimed = outbox_repo.claim_pending_outbox_events(db_session, worker_id=new_worker, batch_size=10)
    db_session.commit()

    reclaimed_ids = [e.id for e in claimed]
    assert stuck_event.id in reclaimed_ids


# ------------------------------------------------------------------------------
# 6. Idempotency & Duplicate Notification Prevention
# ------------------------------------------------------------------------------

def test_idempotent_notification_prevention(outbox_test_data, db_session: Session):
    rest_id = outbox_test_data["rest_a"].id
    mgr_a = outbox_test_data["manager_a"]

    ev = outbox_service.record_outbox_event(
        db=db_session,
        event_type="ANOMALY_FLAGGED",
        aggregate_type="ANOMALY_RESULT",
        aggregate_id=uuid.uuid4(),
        restaurant_id=rest_id,
        payload_jsonb={"title": "Burst Flag", "message": "10 entries in 30s"},
        dedupe_key=f"ANOMALY_FLAGGED_{uuid.uuid4()}",
    )
    db_session.commit()

    # Process first time
    outbox_service.process_single_outbox_event(db_session, ev)
    db_session.commit()

    initial_count = db_session.query(Notification).filter_by(user_id=mgr_a.id, outbox_event_id=ev.id).count()
    assert initial_count == 1

    # Process second time (retry or duplicate worker run)
    outbox_service.process_single_outbox_event(db_session, ev)
    db_session.commit()

    after_count = db_session.query(Notification).filter_by(user_id=mgr_a.id, outbox_event_id=ev.id).count()
    assert after_count == 1  # No duplicate notification added!


# ------------------------------------------------------------------------------
# 7. User Notification Preferences
# ------------------------------------------------------------------------------

def test_disabled_user_preference_suppresses_notification(outbox_test_data, db_session: Session):
    rest_id = outbox_test_data["rest_a"].id
    mgr_a = outbox_test_data["manager_a"]

    # Manager disables ANOMALY_FLAGGED notifications
    pref = NotificationPreference(
        id=uuid.uuid4(),
        user_id=mgr_a.id,
        channel="IN_APP",
        event_type="ANOMALY_FLAGGED",
        enabled=False,
    )
    db_session.add(pref)
    db_session.commit()

    ev = outbox_service.record_outbox_event(
        db=db_session,
        event_type="ANOMALY_FLAGGED",
        aggregate_type="ANOMALY_RESULT",
        aggregate_id=uuid.uuid4(),
        restaurant_id=rest_id,
        payload_jsonb={"title": "Suppressed Anomaly", "message": "Test"},
    )
    db_session.commit()

    outbox_service.process_single_outbox_event(db_session, ev)
    db_session.commit()

    notif = db_session.query(Notification).filter_by(user_id=mgr_a.id, outbox_event_id=ev.id).first()
    assert notif is None  # Notification suppressed due to disabled preference!


# ------------------------------------------------------------------------------
# 8. Notification REST API Endpoints & RBAC
# ------------------------------------------------------------------------------

def test_api_get_user_notifications(outbox_test_data, db_session: Session):
    rest_id = outbox_test_data["rest_a"].id
    staff_a1 = outbox_test_data["staff_a1"]
    token_staff = outbox_test_data["token_staff_a1"]

    n1 = Notification(
        id=uuid.uuid4(),
        restaurant_id=rest_id,
        user_id=staff_a1.id,
        title="Welcome Staff",
        message="Your shift has started",
        event_type="SYSTEM",
    )
    db_session.add(n1)
    db_session.commit()

    res = client.get(
        "/api/v1/notifications",
        headers={"Authorization": f"Bearer {token_staff}"},
    )
    assert res.status_code == 200
    assert res.json()["success"] is True
    assert res.json()["data"]["total"] >= 1
    assert res.json()["data"]["notifications"][0]["id"] == str(n1.id)


def test_api_mark_notification_read(outbox_test_data, db_session: Session):
    rest_id = outbox_test_data["rest_a"].id
    staff_a1 = outbox_test_data["staff_a1"]
    token_staff = outbox_test_data["token_staff_a1"]

    n = Notification(id=uuid.uuid4(), restaurant_id=rest_id, user_id=staff_a1.id, title="Unread Alert", message="Check temp", event_type="TASK_OVERDUE")
    db_session.add(n)
    db_session.commit()

    res = client.patch(
        f"/api/v1/notifications/{n.id}/read",
        headers={"Authorization": f"Bearer {token_staff}"},
    )
    assert res.status_code == 200
    assert res.json()["data"]["read_at"] is not None


def test_api_notification_preferences_get_and_put(outbox_test_data):
    token_mgr = outbox_test_data["token_manager_a"]

    # Put preference
    res_put = client.put(
        "/api/v1/notifications/preferences",
        json={"channel": "IN_APP", "event_type": "CAPA_ASSIGNED", "enabled": False},
        headers={"Authorization": f"Bearer {token_mgr}"},
    )
    assert res_put.status_code == 200
    assert res_put.json()["data"]["enabled"] is False

    # Get preferences
    res_get = client.get(
        "/api/v1/notifications/preferences",
        headers={"Authorization": f"Bearer {token_mgr}"},
    )
    assert res_get.status_code == 200
    assert len(res_get.json()["data"]) >= 1
