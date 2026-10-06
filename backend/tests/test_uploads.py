import hashlib
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.main import app
from app.models.identity import Restaurant, Role, User, UserRole
from app.models.tasks_and_rules import EvidenceFile

client = TestClient(app)

# Standard binary test fixtures
VALID_JPEG_BYTES = b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xFF\xDB\x00C\x00"
VALID_PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
VALID_WEBP_BYTES = b"RIFF\x1a\x00\x00\x00WEBPVP8 \x0e\x00\x00\x00\x30\x01\x00\x9d\x01\x2a\x01\x00\x01\x00"
FAKE_EXE_BYTES = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00"
TEXT_SCRIPT_BYTES = b"#!/bin/bash\necho 'Hacked'\n"


@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def upload_test_data(db_session: Session):
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

    # Restaurant A & B
    rest_a = Restaurant(
        id=uuid.uuid4(),
        name=f"Upload Test Kitchen A {uuid.uuid4().hex[:4]}",
        category="RESTAURANT",
        address_line1="123 Upload St",
        city="Bengaluru",
        state="Karnataka",
        pincode="560001",
        status="ACTIVE",
    )
    db_session.add(rest_a)

    rest_b = Restaurant(
        id=uuid.uuid4(),
        name=f"Upload Test Kitchen B {uuid.uuid4().hex[:4]}",
        category="CLOUD_KITCHEN",
        address_line1="456 Upload St",
        city="Mumbai",
        state="Maharashtra",
        pincode="400001",
        status="ACTIVE",
    )
    db_session.add(rest_b)
    db_session.commit()

    # User A (Staff at Rest A)
    user_a = User(
        id=uuid.uuid4(),
        restaurant_id=rest_a.id,
        name="Staff User A",
        phone=f"+9198{uuid.uuid4().hex[:8]}",
        status="ACTIVE",
    )
    db_session.add(user_a)

    # User B (Manager at Rest B)
    user_b = User(
        id=uuid.uuid4(),
        restaurant_id=rest_b.id,
        name="Manager User B",
        phone=f"+9197{uuid.uuid4().hex[:8]}",
        status="ACTIVE",
    )
    db_session.add(user_b)
    db_session.commit()

    db_session.add(UserRole(id=uuid.uuid4(), user_id=user_a.id, role_id=staff_role.id, restaurant_id=rest_a.id))
    db_session.add(UserRole(id=uuid.uuid4(), user_id=user_b.id, role_id=manager_role.id, restaurant_id=rest_b.id))
    db_session.commit()

    token_a, _ = create_access_token(user_id=user_a.id, tenant_id=rest_a.id, roles=["STAFF"])
    token_b, _ = create_access_token(user_id=user_b.id, tenant_id=rest_b.id, roles=["MANAGER"])

    yield {
        "rest_a": rest_a,
        "rest_b": rest_b,
        "user_a": user_a,
        "user_b": user_b,
        "token_a": token_a,
        "token_b": token_b,
    }

    # Clean up test data
    db_session.query(EvidenceFile).filter(EvidenceFile.restaurant_id.in_([rest_a.id, rest_b.id])).delete(synchronize_session=False)
    db_session.query(UserRole).filter(UserRole.user_id.in_([user_a.id, user_b.id])).delete(synchronize_session=False)
    db_session.query(User).filter(User.id.in_([user_a.id, user_b.id])).delete(synchronize_session=False)
    db_session.query(Restaurant).filter(Restaurant.id.in_([rest_a.id, rest_b.id])).delete(synchronize_session=False)
    db_session.commit()


# ------------------------------------------------------------------------------
# 1. Presign Tests
# ------------------------------------------------------------------------------

def test_presign_upload_success(upload_test_data):
    token = upload_test_data["token_a"]
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "filename": "chiller_temp.jpg",
        "mime_type": "image/jpeg",
        "size_bytes": 1024,
        "purpose": "ENTRY_EVIDENCE",
    }

    res = client.post("/api/v1/uploads/presign", json=payload, headers=headers)
    assert res.status_code == 201
    body = res.json()

    assert body["success"] is True
    data = body["data"]
    assert "id" in data
    assert "upload_url" in data
    assert data["storage_key"].startswith("evidence/")
    assert data["expires_in_seconds"] == 900


def test_presign_unsupported_mime_type_rejected(upload_test_data):
    token = upload_test_data["token_a"]
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "filename": "document.pdf",
        "mime_type": "application/pdf",
        "size_bytes": 2048,
    }

    res = client.post("/api/v1/uploads/presign", json=payload, headers=headers)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_MIME_TYPE"


def test_presign_disallowed_file_extension_rejected(upload_test_data):
    token = upload_test_data["token_a"]
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "filename": "script.sh",
        "mime_type": "image/jpeg",  # Spoofed declared MIME
        "size_bytes": 500,
    }

    res = client.post("/api/v1/uploads/presign", json=payload, headers=headers)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "DISALLOWED_FILE_EXTENSION"


def test_presign_size_exceeded_rejected(upload_test_data):
    token = upload_test_data["token_a"]
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "filename": "large_image.png",
        "mime_type": "image/png",
        "size_bytes": 15 * 1024 * 1024,  # 15MB > 10MB
    }

    res = client.post("/api/v1/uploads/presign", json=payload, headers=headers)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "FILE_SIZE_EXCEEDED"


# ------------------------------------------------------------------------------
# 2. Binary Upload, Magic Bytes & SHA-256 Validation Tests
# ------------------------------------------------------------------------------

@pytest.mark.parametrize("mime_type, filename, binary_content", [
    ("image/jpeg", "test.jpg", VALID_JPEG_BYTES),
    ("image/png", "test.png", VALID_PNG_BYTES),
    ("image/webp", "test.webp", VALID_WEBP_BYTES),
])
def test_valid_image_upload_and_confirmation_flow(upload_test_data, mime_type, filename, binary_content):
    token = upload_test_data["token_a"]
    headers = {"Authorization": f"Bearer {token}"}

    # Step 1: Request presign
    presign_res = client.post(
        "/api/v1/uploads/presign",
        json={"filename": filename, "mime_type": mime_type, "size_bytes": len(binary_content)},
        headers=headers,
    )
    assert presign_res.status_code == 201
    presign_data = presign_res.json()["data"]
    evidence_id = presign_data["id"]
    storage_key = presign_data["storage_key"]

    # Step 2: Upload raw binary to raw upload route
    put_res = client.put(
        f"/api/v1/uploads/raw/{storage_key}",
        content=binary_content,
        headers={"Content-Type": "application/octet-stream"},
    )
    assert put_res.status_code == 200

    # Step 3: Confirm upload
    confirm_res = client.post(f"/api/v1/uploads/{evidence_id}/confirm", headers=headers)
    assert confirm_res.status_code == 200
    confirm_data = confirm_res.json()["data"]

    assert confirm_data["upload_status"] == "COMPLETED"
    assert confirm_data["mime_type"] == mime_type
    assert confirm_data["size_bytes"] == len(binary_content)

    # Verify computed SHA-256 matches actual content SHA-256
    expected_sha256 = hashlib.sha256(binary_content).hexdigest()
    assert confirm_data["sha256"] == expected_sha256


def test_invalid_magic_bytes_rejected_on_confirm(upload_test_data):
    token = upload_test_data["token_a"]
    headers = {"Authorization": f"Bearer {token}"}

    # Presign claiming image/jpeg
    presign_res = client.post(
        "/api/v1/uploads/presign",
        json={"filename": "fake_image.jpg", "mime_type": "image/jpeg", "size_bytes": len(TEXT_SCRIPT_BYTES)},
        headers=headers,
    )
    evidence_id = presign_res.json()["data"]["id"]
    storage_key = presign_res.json()["data"]["storage_key"]

    # Upload text script bytes instead of JPEG
    client.put(
        f"/api/v1/uploads/raw/{storage_key}",
        content=TEXT_SCRIPT_BYTES,
        headers={"Content-Type": "application/octet-stream"},
    )

    # Confirm should detect magic byte mismatch and REJECT
    confirm_res = client.post(f"/api/v1/uploads/{evidence_id}/confirm", headers=headers)
    assert confirm_res.status_code == 400
    assert confirm_res.json()["error"]["code"] == "INVALID_FILE_TYPE"

    # Verify status in DB updated to FAILED
    get_res = client.get(f"/api/v1/uploads/{evidence_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["data"]["upload_status"] == "FAILED"


def test_confirm_without_uploading_returns_404(upload_test_data):
    token = upload_test_data["token_a"]
    headers = {"Authorization": f"Bearer {token}"}

    # Presign without performing raw binary upload
    presign_res = client.post(
        "/api/v1/uploads/presign",
        json={"filename": "missing.jpg", "mime_type": "image/jpeg", "size_bytes": 500},
        headers=headers,
    )
    evidence_id = presign_res.json()["data"]["id"]

    confirm_res = client.post(f"/api/v1/uploads/{evidence_id}/confirm", headers=headers)
    assert confirm_res.status_code == 404
    assert confirm_res.json()["error"]["code"] == "FILE_NOT_FOUND_IN_STORAGE"


def test_confirm_idempotent_on_completed_file(upload_test_data):
    token = upload_test_data["token_a"]
    headers = {"Authorization": f"Bearer {token}"}

    presign_res = client.post(
        "/api/v1/uploads/presign",
        json={"filename": "photo.png", "mime_type": "image/png", "size_bytes": len(VALID_PNG_BYTES)},
        headers=headers,
    )
    evidence_id = presign_res.json()["data"]["id"]
    storage_key = presign_res.json()["data"]["storage_key"]

    client.put(f"/api/v1/uploads/raw/{storage_key}", content=VALID_PNG_BYTES)

    # Confirm #1
    res1 = client.post(f"/api/v1/uploads/{evidence_id}/confirm", headers=headers)
    assert res1.status_code == 200

    # Confirm #2 (Idempotence check)
    res2 = client.post(f"/api/v1/uploads/{evidence_id}/confirm", headers=headers)
    assert res2.status_code == 200
    assert res2.json()["data"]["id"] == res1.json()["data"]["id"]
    assert res2.json()["data"]["upload_status"] == "COMPLETED"


# ------------------------------------------------------------------------------
# 3. Tenant Isolation & Authorization Tests
# ------------------------------------------------------------------------------

def test_tenant_isolation_cross_tenant_access_denied(upload_test_data):
    token_a = upload_test_data["token_a"]
    token_b = upload_test_data["token_b"]

    # User A (Restaurant A) creates presign & confirms upload
    presign_res = client.post(
        "/api/v1/uploads/presign",
        json={"filename": "private.jpg", "mime_type": "image/jpeg", "size_bytes": len(VALID_JPEG_BYTES)},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    evidence_id = presign_res.json()["data"]["id"]
    storage_key = presign_res.json()["data"]["storage_key"]
    client.put(f"/api/v1/uploads/raw/{storage_key}", content=VALID_JPEG_BYTES)

    # User B (Restaurant B) attempts to confirm -> FORBIDDEN (403)
    confirm_b = client.post(
        f"/api/v1/uploads/{evidence_id}/confirm",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert confirm_b.status_code == 403
    assert confirm_b.json()["error"]["code"] == "FORBIDDEN_CROSS_TENANT"

    # User B attempts GET metadata -> FORBIDDEN (403)
    get_b = client.get(
        f"/api/v1/uploads/{evidence_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert get_b.status_code == 403


def test_download_completed_evidence_file(upload_test_data):
    token = upload_test_data["token_a"]
    headers = {"Authorization": f"Bearer {token}"}

    presign_res = client.post(
        "/api/v1/uploads/presign",
        json={"filename": "preview.png", "mime_type": "image/png", "size_bytes": len(VALID_PNG_BYTES)},
        headers=headers,
    )
    evidence_id = presign_res.json()["data"]["id"]
    storage_key = presign_res.json()["data"]["storage_key"]

    client.put(f"/api/v1/uploads/raw/{storage_key}", content=VALID_PNG_BYTES)
    client.post(f"/api/v1/uploads/{evidence_id}/confirm", headers=headers)

    # Download file binary
    file_res = client.get(f"/api/v1/uploads/{evidence_id}/file", headers=headers)
    assert file_res.status_code == 200
    assert file_res.headers["content-type"].startswith("image/png")
    assert file_res.content == VALID_PNG_BYTES
