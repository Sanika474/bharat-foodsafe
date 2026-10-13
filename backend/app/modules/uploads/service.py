import re
import uuid
from pathlib import Path
from sqlalchemy.orm import Session
from app.core.exceptions import AppException
from app.core.tenant import TenantContext
from app.modules.uploads import repository, storage
from app.modules.uploads.schema import EvidenceFileResponse, PresignRequest, PresignResponse


def sanitize_filename(filename: str) -> str:
    """Sanitizes raw filenames to prevent path traversal and unsafe characters."""
    clean_name = Path(filename).name
    clean_name = re.sub(r"[^\w\.\-]", "_", clean_name)
    return clean_name or "file.bin"


def request_presigned_upload(
    db: Session,
    tenant_ctx: TenantContext,
    req: PresignRequest,
    base_url: str = "http://localhost:8000",
) -> PresignResponse:
    # 1. Validate size limit
    if req.size_bytes <= 0:
        raise AppException(
            code="INVALID_FILE_SIZE",
            message="File size must be greater than 0 bytes.",
            status_code=400,
        )
    if req.size_bytes > storage.MAX_UPLOAD_BYTES:
        raise AppException(
            code="FILE_SIZE_EXCEEDED",
            message=f"Declared file size ({req.size_bytes} bytes) exceeds maximum limit of 10MB.",
            status_code=400,
        )

    # 2. Validate declared MIME type
    if req.mime_type not in storage.ALLOWED_MIME_TYPES:
        raise AppException(
            code="INVALID_MIME_TYPE",
            message=f"Unsupported declared MIME type '{req.mime_type}'. Allowed types: image/jpeg, image/png, image/webp.",
            status_code=400,
        )

    # 3. Check filename extension security
    clean_filename = sanitize_filename(req.filename)
    ext = Path(clean_filename).suffix.lower()
    if ext in storage.DISALLOWED_EXTENSIONS:
        raise AppException(
            code="DISALLOWED_FILE_EXTENSION",
            message=f"File extension '{ext}' is prohibited for security reasons.",
            status_code=400,
        )

    # 4. Resolve tenant access
    target_restaurant_id = req.restaurant_id or tenant_ctx.restaurant_id
    if not target_restaurant_id:
        raise AppException(
            code="TENANT_ID_REQUIRED",
            message="restaurant_id is required to request evidence upload presign.",
            status_code=400,
        )

    tenant_ctx.validate_tenant_access(target_restaurant_id)

    # 5. Generate unique storage key
    unique_file_id = uuid.uuid4()
    storage_key = f"evidence/{target_restaurant_id}/{unique_file_id}/{clean_filename}"

    # 6. Create DB record in PENDING status
    evidence = repository.create_evidence_file(
        db=db,
        restaurant_id=target_restaurant_id,
        uploaded_by=tenant_ctx.user_id,
        storage_key=storage_key,
        original_filename=clean_filename,
        mime_type=req.mime_type,
        size_bytes=req.size_bytes,
        upload_status="PENDING",
    )

    db.commit()

    # 7. Construct upload presigned URL (Local storage raw upload route)
    clean_base_url = base_url.rstrip("/")
    upload_url = f"{clean_base_url}/api/v1/uploads/raw/{storage_key}"

    return PresignResponse(
        id=evidence.id,
        upload_url=upload_url,
        storage_key=storage_key,
        expires_in_seconds=900,
    )


def save_raw_binary_content(storage_key: str, content: bytes) -> None:
    """Saves raw uploaded binary payload to storage location."""
    storage.save_file_to_local_storage(storage_key, content)


def confirm_evidence_upload(
    db: Session,
    tenant_ctx: TenantContext,
    evidence_file_id: uuid.UUID,
) -> EvidenceFileResponse:
    # 1. Fetch evidence record
    evidence = repository.get_evidence_file_by_id(db, evidence_file_id)
    if not evidence:
        raise AppException(
            code="EVIDENCE_NOT_FOUND",
            message=f"Evidence file record '{evidence_file_id}' not found.",
            status_code=404,
        )

    # 2. Validate tenant access
    tenant_ctx.validate_tenant_access(evidence.restaurant_id)

    # 3. Idempotency check: Return existing completed record
    if evidence.upload_status == "COMPLETED":
        return EvidenceFileResponse.model_validate(evidence)

    # 4. Check file existence in storage
    if not storage.file_exists_in_storage(evidence.storage_key):
        repository.update_evidence_file_status(db, evidence, upload_status="FAILED")
        db.commit()
        raise AppException(
            code="FILE_NOT_FOUND_IN_STORAGE",
            message="Binary file has not been uploaded to the specified storage location.",
            status_code=404,
        )

    # 5. Read binary content
    content = storage.read_file_from_local_storage(evidence.storage_key)
    actual_size = len(content)

    # 6. Binary validation: Size limits
    if actual_size <= 0:
        repository.update_evidence_file_status(db, evidence, upload_status="FAILED")
        db.commit()
        raise AppException(
            code="EMPTY_FILE",
            message="Uploaded binary file is empty (0 bytes).",
            status_code=400,
        )
    if actual_size > storage.MAX_UPLOAD_BYTES:
        repository.update_evidence_file_status(db, evidence, upload_status="FAILED")
        db.commit()
        raise AppException(
            code="FILE_SIZE_EXCEEDED",
            message=f"Uploaded binary file size ({actual_size} bytes) exceeds maximum 10MB limit.",
            status_code=400,
        )

    # 7. Binary validation: Magic bytes / Header inspection
    detected_mime = storage.detect_mime_type(content)
    if not detected_mime:
        repository.update_evidence_file_status(db, evidence, upload_status="FAILED")
        db.commit()
        raise AppException(
            code="INVALID_FILE_TYPE",
            message="Binary header magic-bytes do not match allowed image formats (JPEG, PNG, WebP). Client-declared MIME type rejected.",
            status_code=400,
        )

    # 8. Compute SHA-256 Checksum
    computed_sha256 = storage.calculate_sha256(content)

    # 9. Mark upload COMPLETED
    updated_evidence = repository.update_evidence_file_status(
        db=db,
        evidence=evidence,
        upload_status="COMPLETED",
        mime_type=detected_mime,
        size_bytes=actual_size,
        sha256=computed_sha256,
    )

    db.commit()

    return EvidenceFileResponse.model_validate(updated_evidence)


def get_evidence_file_details(
    db: Session,
    tenant_ctx: TenantContext,
    evidence_file_id: uuid.UUID,
) -> EvidenceFileResponse:
    evidence = repository.get_evidence_file_by_id(db, evidence_file_id)
    if not evidence:
        raise AppException(
            code="EVIDENCE_NOT_FOUND",
            message=f"Evidence file '{evidence_file_id}' not found.",
            status_code=404,
        )

    tenant_ctx.validate_tenant_access(evidence.restaurant_id)
    return EvidenceFileResponse.model_validate(evidence)


def get_evidence_file_binary(
    db: Session,
    tenant_ctx: TenantContext,
    evidence_file_id: uuid.UUID,
) -> tuple[bytes, str, str]:
    evidence = repository.get_evidence_file_by_id(db, evidence_file_id)
    if not evidence:
        raise AppException(
            code="EVIDENCE_NOT_FOUND",
            message=f"Evidence file '{evidence_file_id}' not found.",
            status_code=404,
        )

    tenant_ctx.validate_tenant_access(evidence.restaurant_id)

    if evidence.upload_status != "COMPLETED":
        raise AppException(
            code="EVIDENCE_NOT_AVAILABLE",
            message=f"Evidence file is in '{evidence.upload_status}' status and cannot be downloaded.",
            status_code=400,
        )

    content = storage.read_file_from_local_storage(evidence.storage_key)
    return content, evidence.mime_type, evidence.original_filename
