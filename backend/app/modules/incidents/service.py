import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.core.tenant import TenantContext
from app.models.analytics_and_incidents import CorrectiveAction, Incident
from app.models.tasks_and_rules import Entry, Task
from app.modules.incidents import repository
from app.modules.incidents.schema import (
    AssignCAPARequest,
    CompleteCAPARequest,
    CorrectiveActionResponse,
    IncidentResponse,
    VerifyCAPARequest,
)


def trigger_critical_deviation_incident(
    db: Session,
    entry: Entry,
    task: Task,
    evaluation_details: list | None = None,
) -> Incident:
    """
    Automatically creates an OPEN Incident and OPEN CAPA when a task-entry safety evaluation is CRITICAL.
    Prevent duplicate incident/CAPA creation when the same entry is processed repeatedly.
    """
    # 1. Deduplication / Idempotency check
    existing_incident = repository.get_incident_by_entry_id(db, entry.id)
    if existing_incident:
        return existing_incident

    task_name = task.template.name if task and task.template else "Task"

    # Build descriptive detail summary from critical evaluation rules
    crit_reasons = []
    if evaluation_details:
        for d in evaluation_details:
            outcome = getattr(d, "outcome", None) or d.get("outcome") if isinstance(d, dict) else None
            reason = getattr(d, "reason", None) or d.get("reason") if isinstance(d, dict) else None
            if outcome == "CRITICAL" and reason:
                crit_reasons.append(reason)

    description = " | ".join(crit_reasons) if crit_reasons else f"Critical food safety boundary breached during task '{task_name}' execution."

    # 2. Create Incident row (status='OPEN', severity='CRITICAL')
    incident = repository.create_incident(
        db=db,
        restaurant_id=entry.restaurant_id,
        entry_id=entry.id,
        title=f"CRITICAL SAFETY DEVIATION: Task '{task_name}' breach",
        description=description,
        severity="CRITICAL",
        status="OPEN",
        detected_by=entry.user_id,
    )

    # 3. Create initial CorrectiveAction (CAPA) row (status='PENDING')
    repository.create_corrective_action(
        db=db,
        incident_id=incident.id,
        action_text=f"Investigate critical safety deviation for task '{task_name}' and submit verified re-check entry.",
        assigned_to=None,
        status="PENDING",
    )

    db.flush()
    return incident


def start_incident(
    db: Session,
    tenant_ctx: TenantContext,
    incident_id: uuid.UUID,
) -> IncidentResponse:
    incident = repository.get_incident_by_id(db, incident_id)
    if not incident:
        raise AppException(code="INCIDENT_NOT_FOUND", message=f"Incident '{incident_id}' not found.", status_code=404)

    tenant_ctx.validate_tenant_access(incident.restaurant_id)

    if incident.status == "OPEN":
        repository.update_incident_status(db, incident, status="INVESTIGATING")
        db.commit()

    return IncidentResponse.model_validate(incident)


def assign_corrective_action(
    db: Session,
    tenant_ctx: TenantContext,
    ca_id: uuid.UUID,
    req: AssignCAPARequest,
) -> CorrectiveActionResponse:
    ca = repository.get_corrective_action_by_id(db, ca_id)
    if not ca:
        raise AppException(code="CAPA_NOT_FOUND", message=f"Corrective action '{ca_id}' not found.", status_code=404)

    tenant_ctx.validate_tenant_access(ca.incident.restaurant_id)

    # Only Manager / Platform Admin can assign CAPA
    if not ("MANAGER" in tenant_ctx.roles or tenant_ctx.is_platform_admin()):
        raise AppException(code="INSUFFICIENT_PERMISSIONS", message="Only managers can assign corrective actions.", status_code=403)

    action_text = req.action_text or ca.action_text

    repository.update_corrective_action(
        db=db,
        ca=ca,
        status="IN_PROGRESS",
        assigned_to=req.assigned_to,
        notes=action_text,
    )

    # Move incident status to INVESTIGATING if OPEN
    if ca.incident.status in ("OPEN", "RESOLVED"):
        repository.update_incident_status(db, ca.incident, status="INVESTIGATING")

    db.commit()
    return CorrectiveActionResponse.model_validate(ca)


def complete_corrective_action_recheck(
    db: Session,
    tenant_ctx: TenantContext,
    ca_id: uuid.UUID,
    req: CompleteCAPARequest,
) -> CorrectiveActionResponse:
    """
    Staff/Manager completes CAPA by submitting a re-check reading and optional evidence photo.
    Evaluates safety rules on re-check entry. If re-check is still CRITICAL, rejects action and reverts status.
    """
    ca = repository.get_corrective_action_by_id(db, ca_id)
    if not ca:
        raise AppException(code="CAPA_NOT_FOUND", message=f"Corrective action '{ca_id}' not found.", status_code=404)

    incident = ca.incident
    tenant_ctx.validate_tenant_access(incident.restaurant_id)

    # Assignment check: if assigned to specific staff, check user
    is_manager_or_admin = "MANAGER" in tenant_ctx.roles or tenant_ctx.is_platform_admin()
    if not is_manager_or_admin:
        if ca.assigned_to and ca.assigned_to != tenant_ctx.user_id:
            raise AppException(code="TASK_ASSIGNMENT_DENIED", message="User is not assigned to this corrective action.", status_code=403)

    # 1. Fetch original task to associate recheck entry
    original_entry = incident.entry
    if not original_entry:
        raise AppException(code="ENTRY_NOT_FOUND", message="Original entry associated with incident not found.", status_code=404)

    task = original_entry.task

    # Validate template evidence requirement if applicable
    template_version = task.template_version
    config = template_version.configuration_jsonb if template_version and template_version.configuration_jsonb else {}
    if config.get("requires_evidence", False) and not req.evidence_file_id:
        raise AppException(
            code="ENTRY_EVIDENCE_REQUIRED",
            message="Photo evidence is required for this re-check.",
            status_code=422,
            details=[{"field": "evidence_file_id", "issue": "Field cannot be null for tasks requiring physical photo verification."}],
        )

    # 2. Create Re-check Entry
    from app.modules.tasks import repository as task_repo
    recheck_entry = task_repo.create_entry(
        db=db,
        restaurant_id=incident.restaurant_id,
        task_id=task.id,
        user_id=tenant_ctx.user_id,
        equipment_id=original_entry.equipment_id,
        evidence_file_id=req.evidence_file_id,
        idempotency_key_id=None,
        value_numeric=req.value_numeric,
        value_text=req.value_text,
        value_jsonb=req.value_jsonb,
        unit=req.unit or original_entry.unit,
        safety_status="NORMAL",
    )

    # 3. Run Deterministic Safety Rules Engine on re-check reading
    from app.modules.safety_rules.engine import evaluate_and_persist_entry_safety
    recheck_result = evaluate_and_persist_entry_safety(db, recheck_entry, task)

    # 4. Check Re-check Safety Evaluation Outcome
    if recheck_result.overall_status == "CRITICAL":
        # Requirement E3.2: Recheck value is still in CRITICAL deviation range!
        repository.update_corrective_action(
            db=db,
            ca=ca,
            status="REJECTED",
            recheck_entry_id=recheck_entry.id,
            evidence_file_id=req.evidence_file_id,
            notes=req.notes or "Re-check reading is still in CRITICAL deviation range.",
        )
        repository.update_incident_status(db, incident, status="INVESTIGATING")
        db.commit()

        raise AppException(
            code="RECHECK_STILL_CRITICAL",
            message="Re-check value is still in CRITICAL deviation range. Action cannot be completed.",
            status_code=422,
            details=[{"field": "value", "issue": "Re-check value breached critical safety threshold."}],
        )

    # Recheck Passed (NORMAL or DEVIATION) -> Transition CAPA status to VERIFIED (or ready for manager verification)
    repository.update_corrective_action(
        db=db,
        ca=ca,
        status="VERIFIED",
        recheck_entry_id=recheck_entry.id,
        evidence_file_id=req.evidence_file_id,
        notes=req.notes,
    )
    repository.update_incident_status(db, incident, status="RESOLVED")

    db.commit()
    return CorrectiveActionResponse.model_validate(ca)


def verify_corrective_action(
    db: Session,
    tenant_ctx: TenantContext,
    ca_id: uuid.UUID,
    req: VerifyCAPARequest,
) -> CorrectiveActionResponse:
    """
    Manager verifies CAPA resolution and evidence.
    If approved -> Incident moves to CLOSED.
    If rejected -> CAPA reverts to IN_PROGRESS and Incident returns to INVESTIGATING.
    """
    ca = repository.get_corrective_action_by_id(db, ca_id)
    if not ca:
        raise AppException(code="CAPA_NOT_FOUND", message=f"Corrective action '{ca_id}' not found.", status_code=404)

    incident = ca.incident
    tenant_ctx.validate_tenant_access(incident.restaurant_id)

    # Only Manager / Platform Admin can verify
    if not ("MANAGER" in tenant_ctx.roles or tenant_ctx.is_platform_admin()):
        raise AppException(code="INSUFFICIENT_PERMISSIONS", message="Only managers can verify corrective actions.", status_code=403)

    if req.approved:
        # Verified & Approved -> Close Incident
        now = datetime.now(timezone.utc)
        repository.update_corrective_action(
            db=db,
            ca=ca,
            status="VERIFIED",
            verified_by=tenant_ctx.user_id,
            verified_at=now,
            notes=req.notes or ca.notes,
        )
        repository.update_incident_status(db, incident, status="CLOSED", resolved_at=now)
    else:
        # Manager Reopens Resolved CAPA (e.g. Evidence illegible)
        repository.update_corrective_action(
            db=db,
            ca=ca,
            status="IN_PROGRESS",
            notes=req.notes or "Manager rejected verification. Please upload legible photo and re-submit.",
        )
        repository.update_incident_status(db, incident, status="INVESTIGATING", resolved_at=None)

    db.commit()
    return CorrectiveActionResponse.model_validate(ca)


def prohibit_direct_status_patch():
    """Requirement E3.1: Direct PATCH status updates to CLOSED are prohibited."""
    raise AppException(
        code="DIRECT_STATUS_MUTATION_PROHIBITED",
        message="Direct status updates are prohibited. Incidents must be closed via verified CAPA re-check.",
        status_code=409,
    )


def list_incidents(
    db: Session,
    tenant_ctx: TenantContext,
    status: str | None = None,
    severity: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[IncidentResponse], int]:
    restaurant_id = None if tenant_ctx.is_platform_admin() else tenant_ctx.restaurant_id
    incidents, total = repository.list_incidents(db, restaurant_id=restaurant_id, status=status, severity=severity, skip=skip, limit=limit)
    return [IncidentResponse.model_validate(inc) for inc in incidents], total


def get_incident_by_id(
    db: Session,
    tenant_ctx: TenantContext,
    incident_id: uuid.UUID,
) -> IncidentResponse:
    incident = repository.get_incident_by_id(db, incident_id)
    if not incident:
        raise AppException(code="INCIDENT_NOT_FOUND", message=f"Incident '{incident_id}' not found.", status_code=404)
    tenant_ctx.validate_tenant_access(incident.restaurant_id)
    return IncidentResponse.model_validate(incident)


def list_corrective_actions(
    db: Session,
    tenant_ctx: TenantContext,
    status: str | None = None,
    assigned_to: uuid.UUID | None = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[CorrectiveActionResponse], int]:
    restaurant_id = None if tenant_ctx.is_platform_admin() else tenant_ctx.restaurant_id
    cas, total = repository.list_corrective_actions(db, restaurant_id=restaurant_id, status=status, assigned_to=assigned_to, skip=skip, limit=limit)
    return [CorrectiveActionResponse.model_validate(ca) for ca in cas], total


def get_corrective_action_by_id(
    db: Session,
    tenant_ctx: TenantContext,
    ca_id: uuid.UUID,
) -> CorrectiveActionResponse:
    ca = repository.get_corrective_action_by_id(db, ca_id)
    if not ca:
        raise AppException(code="CAPA_NOT_FOUND", message=f"Corrective action '{ca_id}' not found.", status_code=404)
    tenant_ctx.validate_tenant_access(ca.incident.restaurant_id)
    return CorrectiveActionResponse.model_validate(ca)
