import uuid
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_code = Column(String(80), nullable=False)
    version_number = Column(Integer, nullable=False)
    algorithm = Column(String(80), nullable=False)
    parameters_jsonb = Column(JSONB, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class AnomalyResult(Base):
    __tablename__ = "anomaly_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entry_id = Column(UUID(as_uuid=True), ForeignKey("entries.id", ondelete="CASCADE"), nullable=False)
    model_version_id = Column(UUID(as_uuid=True), ForeignKey("model_versions.id", ondelete="RESTRICT"), nullable=True)
    baseline_score = Column(Float, nullable=True)
    ml_score = Column(Float, nullable=True)
    decision = Column(String(20), nullable=False, default="NO_FLAG")
    reasons_jsonb = Column(JSONB, nullable=True)
    analyzed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    entry = relationship("Entry", backref="anomaly_results")
    model_version = relationship("ModelVersion", backref="anomaly_results")

    __table_args__ = (
        CheckConstraint("decision IN ('NO_FLAG','REVIEW','SUSPICIOUS')", name="chk_anomaly_decision"),
    )


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    entry_id = Column(UUID(as_uuid=True), ForeignKey("entries.id", ondelete="RESTRICT"), nullable=True)
    title = Column(String(250), nullable=False)
    description = Column(Text, nullable=True)
    severity = Column(String(20), nullable=False, default="MEDIUM")
    status = Column(String(20), nullable=False, default="OPEN")
    detected_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    restaurant = relationship("Restaurant", backref="incidents")
    entry = relationship("Entry", backref="incidents")
    detector = relationship("User", foreign_keys=[detected_by])

    __table_args__ = (
        CheckConstraint("severity IN ('LOW','MEDIUM','HIGH','CRITICAL')", name="chk_incident_severity"),
        CheckConstraint("status IN ('OPEN','INVESTIGATING','RESOLVED','CLOSED')", name="chk_incident_status"),
    )


class CorrectiveAction(Base):
    __tablename__ = "corrective_actions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id = Column(UUID(as_uuid=True), ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False)
    assigned_to = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    action_text = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="PENDING")
    verified_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    incident = relationship("Incident", backref="corrective_actions")
    assignee = relationship("User", foreign_keys=[assigned_to])
    verifier = relationship("User", foreign_keys=[verified_by])

    __table_args__ = (
        CheckConstraint("status IN ('PENDING','IN_PROGRESS','VERIFIED','REJECTED')", name="chk_ca_status"),
    )


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(200), nullable=False)
    license_no = Column(String(100), nullable=True)
    contact_person = Column(String(120), nullable=True)
    phone = Column(String(20), nullable=True)
    email = Column(String(255), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    restaurant = relationship("Restaurant", backref="suppliers")


class Product(Base):
    __tablename__ = "products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    supplier_id = Column(UUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True)
    name = Column(String(200), nullable=False)
    category = Column(String(80), nullable=False)
    storage_temp_type = Column(String(40), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    restaurant = relationship("Restaurant", backref="products")
    supplier = relationship("Supplier", backref="products")


class Batch(Base):
    __tablename__ = "batches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    supplier_id = Column(UUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=True)
    batch_no = Column(String(100), nullable=False)
    received_date = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expiry_date = Column(DateTime(timezone=True), nullable=True)
    quantity = Column(Numeric(10, 2), nullable=True)
    unit = Column(String(20), nullable=True)
    status = Column(String(20), nullable=False, default="ACCEPTED")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    restaurant = relationship("Restaurant", backref="batches")
    product = relationship("Product", backref="batches")
    supplier = relationship("Supplier", backref="batches")

    __table_args__ = (
        CheckConstraint("status IN ('ACCEPTED','REJECTED','QUARANTINE','EXPIRED')", name="chk_batch_status"),
    )


class BusinessVerification(Base):
    __tablename__ = "business_verifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    fssai_license_no = Column(String(20), nullable=True)
    gstin = Column(String(20), nullable=True)
    verification_status = Column(String(20), nullable=False, default="UNVERIFIED")
    verified_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    restaurant = relationship("Restaurant", backref="business_verifications")

    __table_args__ = (
        CheckConstraint("verification_status IN ('UNVERIFIED','PENDING','VERIFIED','REJECTED')", name="chk_biz_verification_status"),
    )


class VerificationDocument(Base):
    __tablename__ = "verification_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    verification_id = Column(UUID(as_uuid=True), ForeignKey("business_verifications.id", ondelete="CASCADE"), nullable=False)
    evidence_file_id = Column(UUID(as_uuid=True), ForeignKey("evidence_files.id", ondelete="RESTRICT"), nullable=False)
    doc_type = Column(String(80), nullable=False)
    ocr_data_jsonb = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    verification = relationship("BusinessVerification", backref="documents")
    evidence_file = relationship("EvidenceFile", backref="verification_documents")
