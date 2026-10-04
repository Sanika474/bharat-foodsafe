import uuid
from sqlalchemy import text
from app.core.database import SessionLocal
from app.models.identity import Permission, Restaurant, Role, User
from app.models.tasks_and_rules import RuleSource, TaskCategory


def test_database_connection_and_version():
    db = SessionLocal()
    try:
        res = db.execute(text("SELECT version()")).scalar()
        assert "PostgreSQL" in res or "18" in res
    finally:
        db.close()


def test_database_tables_exist():
    db = SessionLocal()
    try:
        tables_res = db.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
        ).scalars().all()
        assert len(tables_res) == 38  # 37 app tables + alembic_version
        assert "restaurants" in tables_res
        assert "users" in tables_res
        assert "roles" in tables_res
        assert "permissions" in tables_res
        assert "tasks" in tables_res
        assert "entries" in tables_res
        assert "incidents" in tables_res
        assert "audit_log" in tables_res
        assert "outbox_events" in tables_res
    finally:
        db.close()


def test_seed_data_validation():
    db = SessionLocal()
    try:
        roles = db.query(Role).all()
        role_names = [r.name for r in roles]
        assert "STAFF" in role_names
        assert "MANAGER" in role_names
        assert "PLATFORM_ADMIN" in role_names

        permissions = db.query(Permission).all()
        assert len(permissions) >= 14

        demo_rest = db.query(Restaurant).filter_by(name="Demo Commercial Kitchen").first()
        assert demo_rest is not None
        assert demo_rest.status == "ACTIVE"
        assert demo_rest.city == "Bengaluru"

        categories = db.query(TaskCategory).all()
        cat_codes = [c.code for c in categories]
        assert "TEMP_LOG" in cat_codes
        assert "HYGIENE" in cat_codes
        assert "RECEIVING" in cat_codes

        rule_source = db.query(RuleSource).filter_by(source_code="FSSAI_SCHEDULE_4").first()
        assert rule_source is not None
        assert rule_source.review_status == "VERIFIED"
    finally:
        db.close()


def test_foreign_key_and_uuid_generation():
    db = SessionLocal()
    try:
        test_rest = Restaurant(
            id=uuid.uuid4(),
            name="FK Test Kitchen",
            category="CLOUD_KITCHEN",
            address_line1="Test St",
            city="Mumbai",
            state="Maharashtra",
            pincode="400001",
            status="ACTIVE",
        )
        db.add(test_rest)
        db.flush()

        test_user = User(
            id=uuid.uuid4(),
            restaurant_id=test_rest.id,
            name="Test Staff User",
            email="teststaff@example.com",
            status="ACTIVE",
        )
        db.add(test_user)
        db.commit()

        fetched_user = db.query(User).filter_by(id=test_user.id).first()
        assert fetched_user is not None
        assert fetched_user.restaurant.name == "FK Test Kitchen"

        # Clean up
        db.delete(test_user)
        db.delete(test_rest)
        db.commit()
    finally:
        db.close()
