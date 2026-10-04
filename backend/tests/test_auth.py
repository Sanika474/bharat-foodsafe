import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.core.exceptions import AppException
from app.core.rate_limit import reset_rate_limit_store
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_pin,
    hash_token,
    verify_password,
    verify_pin,
)
from app.core.tenant import TenantContext
from app.main import app
from app.models.identity import AuthSession, Restaurant, Role, User, UserRole

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_rate_limits():
    reset_rate_limit_store()


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def test_setup_data(db_session: Session):
    # Ensure base roles exist
    staff_role = db_session.query(Role).filter_by(name="STAFF").first()
    if not staff_role:
        staff_role = Role(id=uuid.uuid4(), name="STAFF", is_system_role=True)
        db_session.add(staff_role)

    admin_role = db_session.query(Role).filter_by(name="PLATFORM_ADMIN").first()
    if not admin_role:
        admin_role = Role(id=uuid.uuid4(), name="PLATFORM_ADMIN", is_system_role=True)
        db_session.add(admin_role)

    db_session.commit()

    # Create test restaurant
    restaurant = Restaurant(
        id=uuid.uuid4(),
        name="Auth Test Restaurant",
        category="RESTAURANT",
        address_line1="123 Auth St",
        city="Bengaluru",
        state="Karnataka",
        pincode="560001",
        status="ACTIVE",
    )
    db_session.add(restaurant)
    db_session.commit()

    # Create staff user with Phone + PIN
    staff_user = User(
        id=uuid.uuid4(),
        restaurant_id=restaurant.id,
        name="Staff Rajesh",
        phone="9876543210",
        pin_hash=hash_pin("1234"),
        status="ACTIVE",
    )
    db_session.add(staff_user)

    # Assign STAFF role
    user_role_staff = UserRole(
        id=uuid.uuid4(),
        user_id=staff_user.id,
        role_id=staff_role.id,
        restaurant_id=restaurant.id,
    )
    db_session.add(user_role_staff)

    # Create admin user with Email + Password
    admin_user = User(
        id=uuid.uuid4(),
        restaurant_id=None,
        name="Admin User",
        email="admin@bharatfoodsafe.io",
        password_hash=hash_password("AdminPass123!"),
        status="ACTIVE",
    )
    db_session.add(admin_user)

    # Assign PLATFORM_ADMIN role
    user_role_admin = UserRole(
        id=uuid.uuid4(),
        user_id=admin_user.id,
        role_id=admin_role.id,
        restaurant_id=None,
    )
    db_session.add(user_role_admin)

    # Create suspended staff user
    suspended_user = User(
        id=uuid.uuid4(),
        restaurant_id=restaurant.id,
        name="Suspended Staff",
        phone="9111111111",
        pin_hash=hash_pin("9999"),
        status="SUSPENDED",
    )
    db_session.add(suspended_user)

    db_session.commit()

    yield {
        "restaurant": restaurant,
        "staff_user": staff_user,
        "admin_user": admin_user,
        "suspended_user": suspended_user,
    }

    # Clean up test setup data
    db_session.query(AuthSession).delete()
    db_session.query(UserRole).filter(
        UserRole.user_id.in_([staff_user.id, admin_user.id, suspended_user.id])
    ).delete(synchronize_session=False)
    db_session.query(User).filter(
        User.id.in_([staff_user.id, admin_user.id, suspended_user.id])
    ).delete(synchronize_session=False)
    db_session.query(Restaurant).filter_by(id=restaurant.id).delete()
    db_session.commit()


# ------------------------------------------------------------------------------
# 1. Unit Tests for Hashing and JWT
# ------------------------------------------------------------------------------

def test_password_and_pin_hashing():
    pw = "SecretPassword123"
    hashed_pw = hash_password(pw)
    assert verify_password(pw, hashed_pw) is True
    assert verify_password("WrongPassword", hashed_pw) is False

    pin = "4321"
    hashed_pin_str = hash_pin(pin)
    assert verify_pin(pin, hashed_pin_str) is True
    assert verify_pin("0000", hashed_pin_str) is False

    token = "test_refresh_token_string"
    assert len(hash_token(token)) == 64  # SHA-256 hex string


def test_jwt_token_generation_and_decoding():
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    roles = ["STAFF"]

    token, exp = create_access_token(user_id=user_id, tenant_id=tenant_id, roles=roles)
    decoded = decode_token(token)

    assert decoded["sub"] == str(user_id)
    assert decoded["tenant_id"] == str(tenant_id)
    assert decoded["roles"] == ["STAFF"]
    assert decoded["type"] == "access"

    ref_token, fam_id, sess_id, ref_exp = create_refresh_token(user_id=user_id)
    ref_decoded = decode_token(ref_token)

    assert ref_decoded["sub"] == str(user_id)
    assert ref_decoded["family_id"] == str(fam_id)
    assert ref_decoded["session_id"] == str(sess_id)
    assert ref_decoded["type"] == "refresh"


# ------------------------------------------------------------------------------
# 2. Login Endpoint Tests (/api/v1/auth/login)
# ------------------------------------------------------------------------------

def test_login_staff_phone_pin_success(test_setup_data):
    response = client.post(
        "/api/v1/auth/login",
        json={"phone": "9876543210", "pin": "1234"},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["success"] is True
    assert "access_token" in body["data"]
    assert "refresh_token" in body["data"]
    assert body["data"]["token_type"] == "bearer"
    assert body["data"]["user"]["name"] == "Staff Rajesh"
    assert body["data"]["user"]["roles"] == ["STAFF"]
    assert body["meta"]["request_id"] is not None


def test_login_admin_email_password_success(test_setup_data):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@bharatfoodsafe.io", "password": "AdminPass123!"},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["success"] is True
    assert body["data"]["user"]["name"] == "Admin User"
    assert "PLATFORM_ADMIN" in body["data"]["user"]["roles"]


def test_login_invalid_credentials(test_setup_data):
    # Invalid PIN
    res1 = client.post("/api/v1/auth/login", json={"phone": "9876543210", "pin": "0000"})
    assert res1.status_code == 401
    body1 = res1.json()
    assert body1["success"] is False
    assert body1["error"]["code"] == "INVALID_CREDENTIALS"

    # Non-existent phone
    res2 = client.post("/api/v1/auth/login", json={"phone": "9000000000", "pin": "1234"})
    assert res2.status_code == 401
    assert res2.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_login_suspended_account(test_setup_data):
    res = client.post("/api/v1/auth/login", json={"phone": "9111111111", "pin": "9999"})
    assert res.status_code == 403
    body = res.json()
    assert body["success"] is False
    assert body["error"]["code"] in ["ACCOUNT_SUSPENDED", "ACCOUNT_DISABLED"]


def test_login_rate_limiting():
    # Attempt 5 logins (within limit)
    for _ in range(5):
        client.post("/api/v1/auth/login", json={"phone": "9999999999", "pin": "0000"})

    # 6th attempt should be blocked with 429
    res = client.post("/api/v1/auth/login", json={"phone": "9999999999", "pin": "0000"})
    assert res.status_code == 429
    body = res.json()
    assert body["success"] is False
    assert body["error"]["code"] == "RATE_LIMIT_EXCEEDED"


# ------------------------------------------------------------------------------
# 3. Token Refresh and Reuse Detection Tests (/api/v1/auth/refresh)
# ------------------------------------------------------------------------------

def test_refresh_token_success_and_rotation(test_setup_data, db_session: Session):
    login_res = client.post("/api/v1/auth/login", json={"phone": "9876543210", "pin": "1234"})
    refresh_token = login_res.json()["data"]["refresh_token"]

    # Execute refresh
    refresh_res = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_res.status_code == 200
    ref_body = refresh_res.json()

    assert ref_body["success"] is True
    new_access_token = ref_body["data"]["access_token"]
    new_refresh_token = ref_body["data"]["refresh_token"]

    assert new_access_token != login_res.json()["data"]["access_token"]
    assert new_refresh_token != refresh_token

    # Verify old session in DB is marked revoked and replaced
    old_hash = hash_token(refresh_token)
    old_session = db_session.query(AuthSession).filter_by(refresh_token_hash=old_hash).first()
    assert old_session is not None
    assert old_session.revoked_at is not None
    assert old_session.replaced_by_session_id is not None


def test_refresh_token_reuse_detection(test_setup_data, db_session: Session):
    # Step 1: Initial login
    login_res = client.post("/api/v1/auth/login", json={"phone": "9876543210", "pin": "1234"})
    refresh_token_1 = login_res.json()["data"]["refresh_token"]

    # Step 2: First valid refresh (token_1 -> token_2)
    ref_res1 = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token_1})
    assert ref_res1.status_code == 200
    refresh_token_2 = ref_res1.json()["data"]["refresh_token"]

    # Step 3: Malicious/Duplicate attempt reusing refresh_token_1!
    reuse_res = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token_1})
    assert reuse_res.status_code == 401
    reuse_body = reuse_res.json()
    assert reuse_body["success"] is False
    assert reuse_body["error"]["code"] == "TOKEN_FAMILY_REVOKED"

    # Step 4: Verify that token_2 is now ALSO revoked due to family revocation!
    subsequent_res = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token_2})
    assert subsequent_res.status_code == 401
    assert subsequent_res.json()["error"]["code"] == "TOKEN_FAMILY_REVOKED"


# ------------------------------------------------------------------------------
# 4. Authenticated Endpoints & TenantContext Isolation Tests
# ------------------------------------------------------------------------------

def test_auth_me_endpoint(test_setup_data):
    login_res = client.post("/api/v1/auth/login", json={"phone": "9876543210", "pin": "1234"})
    access_token = login_res.json()["data"]["access_token"]

    me_res = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_res.status_code == 200
    me_body = me_res.json()

    assert me_body["success"] is True
    assert me_body["data"]["name"] == "Staff Rajesh"
    assert "STAFF" in me_body["data"]["roles"]


def test_auth_me_unauthorized():
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"


def test_tenant_context_and_isolation(test_setup_data):
    staff_user = test_setup_data["staff_user"]
    restaurant_id = test_setup_data["restaurant"].id
    other_restaurant_id = uuid.uuid4()

    tenant_ctx = TenantContext(
        user_id=staff_user.id,
        restaurant_id=restaurant_id,
        roles=["STAFF"],
    )

    # Valid tenant access
    tenant_ctx.validate_tenant_access(restaurant_id)

    # Cross-tenant access attempt raises 403 FORBIDDEN_CROSS_TENANT
    with pytest.raises(AppException) as exc_info:
        tenant_ctx.validate_tenant_access(other_restaurant_id)

    assert exc_info.value.code == "FORBIDDEN_CROSS_TENANT"
    assert exc_info.value.status_code == 403
