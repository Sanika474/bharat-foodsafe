import uuid
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


class TaskCategory(Base):
    __tablename__ = "task_categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=True)
    name = Column(String(100), nullable=False)
    code = Column(String(60), nullable=False)
    description = Column(String(255), nullable=True)
    icon = Column(String(80), nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    restaurant = relationship("Restaurant", backref="task_categories")


class RuleSource(Base):
    __tablename__ = "rule_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_code = Column(String(80), unique=True, nullable=False)
    title = Column(String(200), nullable=False)
    issuing_authority = Column(String(120), nullable=False)
    document_reference = Column(String(150), nullable=True)
    effective_date = Column(DateTime(timezone=True), nullable=True)
    review_status = Column(String(30), nullable=False, default="DRAFT")
    verified_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    verifier = relationship("User", foreign_keys=[verified_by])

    __table_args__ = (
        CheckConstraint(
            "review_status IN ('DRAFT','PENDING_REVIEW','VERIFIED','DEPRECATED')",
            name="chk_rule_source_review_status",
        ),
    )


class SafetyRule(Base):
    __tablename__ = "safety_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rule_code = Column(String(80), nullable=False)
    supersedes_rule_id = Column(UUID(as_uuid=True), ForeignKey("safety_rules.id", ondelete="SET NULL"), nullable=True)
    rule_source_id = Column(UUID(as_uuid=True), ForeignKey("rule_sources.id", ondelete="RESTRICT"), nullable=False)
    version_number = Column(Integer, nullable=False, default=1)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    condition_jsonb = Column(JSONB, nullable=False)
    action_jsonb = Column(JSONB, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    superseded_rule = relationship("SafetyRule", remote_side=[id])
    rule_source = relationship("RuleSource", backref="safety_rules")


class SafetyRuleBinding(Base):
    __tablename__ = "safety_rule_bindings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    safety_rule_id = Column(UUID(as_uuid=True), ForeignKey("safety_rules.id", ondelete="CASCADE"), nullable=False)
    category_id = Column(UUID(as_uuid=True), ForeignKey("task_categories.id", ondelete="CASCADE"), nullable=True)
    template_id = Column(UUID(as_uuid=True), ForeignKey("task_templates.id", ondelete="CASCADE"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    safety_rule = relationship("SafetyRule", backref="bindings")
    category = relationship("TaskCategory", backref="rule_bindings")


class TaskTemplate(Base):
    __tablename__ = "task_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    category_id = Column(UUID(as_uuid=True), ForeignKey("task_categories.id", ondelete="RESTRICT"), nullable=False)
    name = Column(String(200), nullable=False)
    code = Column(String(80), nullable=False)
    description = Column(Text, nullable=True)
    frequency_type = Column(String(40), nullable=False, default="DAILY")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    restaurant = relationship("Restaurant", backref="task_templates")
    category = relationship("TaskCategory", backref="task_templates")


class TaskTemplateVersion(Base):
    __tablename__ = "task_template_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id = Column(UUID(as_uuid=True), ForeignKey("task_templates.id", ondelete="CASCADE"), nullable=False)
    version_number = Column(Integer, nullable=False)
    configuration_jsonb = Column(JSONB, nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    template = relationship("TaskTemplate", backref="versions")
    creator = relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        UniqueConstraint("template_id", "version_number", name="uq_task_template_version_number"),
    )


class Equipment(Base):
    __tablename__ = "equipment"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(200), nullable=False)
    equipment_type = Column(String(80), nullable=False)
    location = Column(String(120), nullable=True)
    serial_number = Column(String(100), nullable=True)
    min_temp = Column(Numeric(5, 2), nullable=True)
    max_temp = Column(Numeric(5, 2), nullable=True)
    status = Column(String(30), nullable=False, default="OPERATIONAL")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    restaurant = relationship("Restaurant", backref="equipment")

    __table_args__ = (
        CheckConstraint("status IN ('OPERATIONAL','MAINTENANCE','DECOMMISSIONED')", name="chk_equipment_status"),
    )


class Task(Base):
    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    template_id = Column(UUID(as_uuid=True), ForeignKey("task_templates.id", ondelete="RESTRICT"), nullable=False)
    template_version_id = Column(UUID(as_uuid=True), ForeignKey("task_template_versions.id", ondelete="RESTRICT"), nullable=False)
    occurrence_key = Column(String(100), nullable=False)
    status = Column(String(30), nullable=False, default="PENDING")
    due_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    restaurant = relationship("Restaurant", backref="tasks")
    template = relationship("TaskTemplate", backref="tasks")
    template_version = relationship("TaskTemplateVersion", backref="tasks")

    __table_args__ = (
        CheckConstraint("status IN ('PENDING','IN_PROGRESS','COMPLETED','OVERDUE','MISSED')", name="chk_task_status"),
        UniqueConstraint("template_id", "occurrence_key", name="uq_tasks_template_occurrence"),
    )


class TaskAssignment(Base):
    __tablename__ = "task_assignments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    assigned_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    task = relationship("Task", backref="assignments")
    user = relationship("User", backref="task_assignments")


class EvidenceFile(Base):
    __tablename__ = "evidence_files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    storage_key = Column(String(500), unique=True, nullable=False)
    original_filename = Column(String(255), nullable=False)
    mime_type = Column(String(100), nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    sha256 = Column(String(64), nullable=False)
    upload_status = Column(String(20), nullable=False, default="PENDING")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    restaurant = relationship("Restaurant", backref="evidence_files")
    uploader = relationship("User", foreign_keys=[uploaded_by])

    __table_args__ = (
        CheckConstraint("upload_status IN ('PENDING','COMPLETED','FAILED')", name="chk_evidence_upload_status"),
    )


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    key = Column(String(128), unique=True, nullable=False)
    request_hash = Column(String(64), nullable=False)
    status = Column(String(20), nullable=False, default="PROCESSING")
    response_jsonb = Column(JSONB, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    restaurant = relationship("Restaurant", backref="idempotency_keys")
    user = relationship("User", backref="idempotency_keys")

    __table_args__ = (
        CheckConstraint("status IN ('PROCESSING','COMPLETED','FAILED')", name="chk_idempotency_status"),
    )


class Entry(Base):
    __tablename__ = "entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    restaurant_id = Column(UUID(as_uuid=True), ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="RESTRICT"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    equipment_id = Column(UUID(as_uuid=True), ForeignKey("equipment.id", ondelete="SET NULL"), nullable=True)
    evidence_file_id = Column(UUID(as_uuid=True), ForeignKey("evidence_files.id", ondelete="SET NULL"), nullable=True)
    idempotency_key_id = Column(UUID(as_uuid=True), ForeignKey("idempotency_keys.id", ondelete="SET NULL"), nullable=True)
    value_numeric = Column(Numeric(10, 4), nullable=True)
    value_text = Column(Text, nullable=True)
    value_jsonb = Column(JSONB, nullable=True)
    unit = Column(String(20), nullable=True)
    safety_status = Column(String(20), nullable=False, default="NORMAL")
    recorded_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    restaurant = relationship("Restaurant", backref="entries")
    task = relationship("Task", backref="entries")
    user = relationship("User", backref="entries")
    equipment = relationship("Equipment", backref="entries")
    evidence_file = relationship("EvidenceFile", backref="entries")

    __table_args__ = (
        CheckConstraint("safety_status IN ('NORMAL','DEVIATION','CRITICAL')", name="chk_entry_safety_status"),
    )


class EntrySafetyEvaluation(Base):
    __tablename__ = "entry_safety_evaluations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entry_id = Column(UUID(as_uuid=True), ForeignKey("entries.id", ondelete="CASCADE"), nullable=False)
    safety_rule_id = Column(UUID(as_uuid=True), ForeignKey("safety_rules.id", ondelete="RESTRICT"), nullable=False)
    rule_source_id = Column(UUID(as_uuid=True), ForeignKey("rule_sources.id", ondelete="RESTRICT"), nullable=False)
    evaluation_result = Column(String(40), nullable=False)
    details_jsonb = Column(JSONB, nullable=True)
    evaluated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    entry = relationship("Entry", backref="evaluations")
    safety_rule = relationship("SafetyRule", backref="evaluations")
    rule_source = relationship("RuleSource", backref="evaluations")
