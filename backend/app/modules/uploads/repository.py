import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.tasks_and_rules import EvidenceFile


def get_evidence_file_by_id(db: Session, evidence_file_id: uuid.UUID) -> EvidenceFile | None:
    stmt = select(EvidenceFile).where(EvidenceFile.id == evidence_file_id)
    return db.scalar(stmt)


def get_evidence_file_by_storage_key(db: Session, storage_key: str) -> EvidenceFile | None:
    stmt = select(EvidenceFile).where(EvidenceFile.storage_key == storage_key)
    return db.scalar(stmt)


def create_evidence_file(
    db: Session,
    restaurant_id: uuid.UUID,
    uploaded_by: uuid.UUID,
    storage_key: str,
    original_filename: str,
    mime_type: str,
    size_bytes: int,
    upload_status: str = "PENDING",
) -> EvidenceFile:
    evidence = EvidenceFile(
        id=uuid.uuid4(),
        restaurant_id=restaurant_id,
        uploaded_by=uploaded_by,
        storage_key=storage_key,
        original_filename=original_filename,
        mime_type=mime_type,
        size_bytes=size_bytes,
        sha256="",  # Set upon confirmation
        upload_status=upload_status,
    )
    db.add(evidence)
    db.flush()
    return evidence


def update_evidence_file_status(
    db: Session,
    evidence: EvidenceFile,
    upload_status: str,
    mime_type: str | None = None,
    size_bytes: int | None = None,
    sha256: str | None = None,
) -> EvidenceFile:
    evidence.upload_status = upload_status
    if mime_type is not None:
        evidence.mime_type = mime_type
    if size_bytes is not None:
        evidence.size_bytes = size_bytes
    if sha256 is not None:
        evidence.sha256 = sha256
    db.flush()
    return evidence
