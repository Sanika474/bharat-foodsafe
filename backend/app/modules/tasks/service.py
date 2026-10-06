import hashlib
import json
import uuid
from datetime import date, datetime, timezone
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.exceptions import AppException
from app.core.tenant import TenantContext
from app.jobs.generate_tasks import generate_tasks_for_restaurant
from app.modules.tasks import repository
from app.modules.tasks.schema import (
    EntryResponse,
    TaskEntryCreateRequest,
    TaskGenerateRequest,
    TaskGenerateResult,
    TaskResponse,
)


def generate_scheduled_tasks(
    db: Session,
    tenant_ctx: TenantContext,
    req: TaskGenerateRequest,
) -> TaskGenerateResult:
    target_restaurant_id = req.restaurant_id or tenant_ctx.restaurant_id

    if not target_restaurant_id:
        raise AppException(
            code="TENANT_ID_REQUIRED",
            message="restaurant_id is required to generate task occurrences.",
            status_code=400,
        )

    # Enforce tenant isolation
    tenant_ctx.validate_tenant_access(target_restaurant_id)

    target_date = req.target_date

    return generate_tasks_for_restaurant(
        db=db,
        restaurant_id=target_restaurant_id,
        target_date=target_date,
    )


def list_tasks(
    db: Session,
    tenant_ctx: TenantContext,
    status: str | None = None,
    template_id: uuid.UUID | None = None,
    target_date: date | None = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[TaskResponse], int]:
    filter_restaurant_id = None if tenant_ctx.is_platform_admin() else tenant_ctx.restaurant_id

    tasks, total = repository.list_tasks(
        db=db,
        restaurant_id=filter_restaurant_id,
        status=status,
        template_id=template_id,
        target_date=target_date,
        skip=skip,
        limit=limit,
    )

    task_responses = [TaskResponse.model_validate(t) for t in tasks]
    return task_responses, total


def get_task_by_id(
    db: Session,
    tenant_ctx: TenantContext,
    task_id: uuid.UUID,
) -> TaskResponse:
    task = repository.get_task_by_id(db, task_id)
    if not task:
        raise AppException(
            code="TASK_NOT_FOUND",
            message=f"Task instance '{task_id}' not found.",
            status_code=404,
        )

    tenant_ctx.validate_tenant_access(task.restaurant_id)

    return TaskResponse.model_validate(task)


def execute_task_entry(
    db: Session,
    tenant_ctx: TenantContext,
    task_id: uuid.UUID,
    req: TaskEntryCreateRequest,
    idempotency_key_header: str | None = None,
) -> tuple[dict, bool]:
    """
    Executes a staff task entry submission with persistent idempotency protection.
    Returns a tuple of (response_data_dict, is_replayed).
    """
    # 1. Fetch Task
    task = repository.get_task_by_id(db, task_id)
    if not task:
        raise AppException(
            code="TASK_NOT_FOUND",
            message=f"Task instance '{task_id}' not found.",
            status_code=404,
        )

    # Validate Tenant Scope
    tenant_ctx.validate_tenant_access(task.restaurant_id)

    # Validate Task Assignments (if assigned to specific staff members)
    is_staff_only = "STAFF" in tenant_ctx.roles and not ("MANAGER" in tenant_ctx.roles or tenant_ctx.is_platform_admin())
    if is_staff_only and task.assignments:
        assigned_user_ids = [a.user_id for a in task.assignments]
        if tenant_ctx.user_id not in assigned_user_ids:
            raise AppException(
                code="TASK_ASSIGNMENT_DENIED",
                message="User is not assigned to execute this task.",
                status_code=403,
            )

    # 2. Idempotency Key Setup & Deduplication Check
    idempotency_record = None
    request_hash = ""

    if idempotency_key_header and idempotency_key_header.strip():
        key_str = idempotency_key_header.strip()

        # Compute deterministic request hash
        req_dict = req.model_dump(mode="json")
        request_hash = hashlib.sha256(
            json.dumps(req_dict, sort_keys=True).encode("utf-8")
        ).hexdigest()

        existing_key = repository.get_idempotency_key(db, key_str)
        if existing_key:
            # Tenant check on key
            if existing_key.restaurant_id != task.restaurant_id:
                raise AppException(
                    code="FORBIDDEN_CROSS_TENANT",
                    message="Access denied.",
                    status_code=403,
                )

            # Detect modified payload reuse
            if existing_key.request_hash != request_hash:
                raise AppException(
                    code="IDEMPOTENCY_KEY_REUSE",
                    message="Idempotency key reuse detected with modified payload.",
                    status_code=409,
                )

            if existing_key.status == "COMPLETED":
                # Replay original response!
                return existing_key.response_jsonb or {}, True

            if existing_key.status == "PROCESSING":
                raise AppException(
                    code="IDEMPOTENCY_KEY_PROCESSING",
                    message="A request with this idempotency key is currently processing.",
                    status_code=409,
                )
        else:
            # Create new IdempotencyKey record under nested savepoint to handle concurrency
            try:
                sp = db.begin_nested()
                idempotency_record = repository.create_idempotency_key(
                    db=db,
                    restaurant_id=task.restaurant_id,
                    user_id=tenant_ctx.user_id,
                    key=key_str,
                    request_hash=request_hash,
                    status="PROCESSING",
                )
                sp.commit()
            except IntegrityError:
                db.rollback()
                existing_key = repository.get_idempotency_key(db, key_str)
                if existing_key:
                    if existing_key.request_hash != request_hash:
                        raise AppException(
                            code="IDEMPOTENCY_KEY_REUSE",
                            message="Idempotency key reuse detected with modified payload.",
                            status_code=409,
                        )
                    if existing_key.status == "COMPLETED":
                        return existing_key.response_jsonb or {}, True
                    raise AppException(
                        code="IDEMPOTENCY_KEY_PROCESSING",
                        message="A request with this idempotency key is currently processing.",
                        status_code=409,
                    )
                raise

    # 3. Task Status Check
    if task.status == "COMPLETED":
        raise AppException(
            code="TASK_ALREADY_COMPLETED",
            message="Task has already been completed.",
            status_code=400,
        )

    # 4. Template Requirements & Input Payload Validation
    template_version = task.template_version
    config = template_version.configuration_jsonb if template_version and template_version.configuration_jsonb else {}

    # Check evidence requirement
    requires_evidence = config.get("requires_evidence", False)
    if requires_evidence and not req.evidence_file_id:
        raise AppException(
            code="ENTRY_EVIDENCE_REQUIRED",
            message="Photo evidence is required for this task.",
            status_code=422,
            details=[{"field": "evidence_file_id", "issue": "Field cannot be null for tasks requiring physical photo verification."}],
        )

    if req.evidence_file_id:
        evidence_file = repository.get_evidence_file_by_id(db, req.evidence_file_id)
        if not evidence_file or evidence_file.restaurant_id != task.restaurant_id:
            raise AppException(
                code="EVIDENCE_NOT_FOUND",
                message="Associated evidence file not found or invalid tenant.",
                status_code=404,
            )
        if evidence_file.upload_status != "COMPLETED":
            raise AppException(
                code="EVIDENCE_NOT_AVAILABLE",
                message="Associated evidence upload has not been confirmed or failed.",
                status_code=422,
            )

    # Check equipment requirement
    requires_equipment = config.get("requires_equipment", False)
    if requires_equipment and not req.equipment_id:
        raise AppException(
            code="ENTRY_EQUIPMENT_REQUIRED",
            message="Equipment binding is required for this task.",
            status_code=422,
            details=[{"field": "equipment_id", "issue": "Field cannot be null for tasks requiring bound equipment."}],
        )

    if req.equipment_id:
        equipment = repository.get_equipment_by_id(db, req.equipment_id)
        if not equipment or equipment.restaurant_id != task.restaurant_id:
            raise AppException(
                code="EQUIPMENT_NOT_FOUND",
                message="Bound equipment not found or invalid tenant.",
                status_code=404,
            )

    # Validate observation/value presence
    if req.value_numeric is None and req.value_text is None and req.value_jsonb is None:
        raise AppException(
            code="ENTRY_VALUE_REQUIRED",
            message="At least one measurement or observation value must be provided.",
            status_code=422,
            details=[{"field": "value", "issue": "numeric, text, or jsonb value required"}],
        )

    # 5. Create Entry, Evaluate Deterministic Safety Rules & Update Task Status
    entry = repository.create_entry(
        db=db,
        restaurant_id=task.restaurant_id,
        task_id=task.id,
        user_id=tenant_ctx.user_id,
        equipment_id=req.equipment_id,
        evidence_file_id=req.evidence_file_id,
        idempotency_key_id=idempotency_record.id if idempotency_record else None,
        value_numeric=req.value_numeric,
        value_text=req.value_text,
        value_jsonb=req.value_jsonb,
        unit=req.unit,
        safety_status="NORMAL",
    )

    from app.modules.safety_rules.engine import evaluate_and_persist_entry_safety
    safety_result = evaluate_and_persist_entry_safety(db=db, entry=entry, task=task)

    if entry.safety_status == "CRITICAL":
        from app.modules.incidents.service import trigger_critical_deviation_incident
        trigger_critical_deviation_incident(db=db, entry=entry, task=task, evaluation_details=safety_result.details)

    repository.update_task_status(
        db=db,
        task=task,
        status="COMPLETED",
        completed_at=datetime.now(timezone.utc),
    )

    from app.core.audit import record_audit_event
    record_audit_event(
        db=db,
        event_name="TASK_ENTRY_CREATED",
        resource_type="entry",
        restaurant_id=task.restaurant_id,
        user_id=tenant_ctx.user_id,
        resource_id=entry.id,
        payload_jsonb={
            "task_id": str(task.id),
            "value_numeric": float(entry.value_numeric) if entry.value_numeric is not None else None,
            "unit": entry.unit,
            "safety_status": entry.safety_status,
        },
    )

    from app.modules.anomaly.service import evaluate_entry_anomaly
    evaluate_entry_anomaly(db=db, entry=entry, user_id=tenant_ctx.user_id)

    # 6. Build Response Data Envelope
    response_dto = EntryResponse(
        id=entry.id,
        restaurant_id=entry.restaurant_id,
        task_id=entry.task_id,
        user_id=entry.user_id,
        equipment_id=entry.equipment_id,
        evidence_file_id=entry.evidence_file_id,
        idempotency_key_id=entry.idempotency_key_id,
        value_numeric=float(entry.value_numeric) if entry.value_numeric is not None else None,
        value_text=entry.value_text,
        value_jsonb=entry.value_jsonb,
        unit=entry.unit,
        safety_status=entry.safety_status,
        recorded_at=entry.recorded_at,
        created_at=entry.created_at,
        task_status=task.status,
    )
    response_data = response_dto.model_dump(mode="json")

    # Update idempotency key to COMPLETED if key present
    if idempotency_record:
        repository.update_idempotency_key(
            db=db,
            record=idempotency_record,
            status="COMPLETED",
            response_jsonb=response_data,
        )

    db.commit()

    return response_data, False

