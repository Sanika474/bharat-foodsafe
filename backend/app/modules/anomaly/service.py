import uuid
from sqlalchemy.orm import Session

from app.core.audit import record_audit_event
from app.core.exceptions import AppException
from app.core.tenant import TenantContext
from app.models.analytics_and_incidents import AnomalyResult
from app.models.tasks_and_rules import Entry
from app.modules.anomaly import inference, repository
from app.modules.anomaly.schema import AnomalyQueueItemResponse, AnomalyResultResponse


def evaluate_entry_anomaly(
    db: Session,
    entry: Entry,
    user_id: uuid.UUID | None = None,
) -> AnomalyResult:
    """
    Evaluates statistical anomaly for an entry.
    Prevents duplicate evaluation for the same entry (idempotency).
    If decision is REVIEW, SUSPICIOUS, or ESCALATE, logs ANOMALY_FLAGGED audit event.
    """
    existing = repository.get_anomaly_result_by_entry_id(db, entry.id)
    if existing:
        return existing

    inf_res = inference.run_anomaly_inference(db, entry)

    result = repository.create_anomaly_result(
        db=db,
        entry_id=entry.id,
        decision=inf_res["decision"],
        ml_score=inf_res["ml_score"],
        baseline_score=inf_res["baseline_score"],
        reasons_jsonb=inf_res["reasons_jsonb"],
    )

    if result.decision in ("REVIEW", "SUSPICIOUS", "ESCALATE"):
        record_audit_event(
            db=db,
            event_name="ANOMALY_FLAGGED",
            resource_type="anomaly_result",
            restaurant_id=entry.restaurant_id,
            user_id=user_id or entry.user_id,
            resource_id=result.id,
            payload_jsonb={
                "entry_id": str(entry.id),
                "decision": result.decision,
                "ml_score": result.ml_score,
                "reasons": inf_res["reasons_jsonb"].get("flags", []),
            },
        )

    db.flush()
    return result


def list_anomalies(
    db: Session,
    tenant_ctx: TenantContext,
    decision: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[AnomalyQueueItemResponse], int]:
    restaurant_id = None if tenant_ctx.is_platform_admin() else tenant_ctx.restaurant_id
    results, total = repository.list_anomaly_results(
        db=db,
        restaurant_id=restaurant_id,
        decision=decision,
        skip=skip,
        limit=limit,
    )

    items = []
    for res in results:
        entry = res.entry
        task_name = entry.task.template.name if entry and entry.task and entry.task.template else "Task Entry"
        user_name = entry.user.name if entry and entry.user else "Kitchen Staff"
        items.append(
            AnomalyQueueItemResponse(
                id=res.id,
                entry_id=res.entry_id,
                restaurant_id=entry.restaurant_id,
                task_name=task_name,
                user_name=user_name,
                decision=res.decision,
                ml_score=res.ml_score,
                baseline_score=res.baseline_score,
                reasons_jsonb=res.reasons_jsonb,
                analyzed_at=res.analyzed_at,
            )
        )

    return items, total


def get_anomaly_by_id(
    db: Session,
    tenant_ctx: TenantContext,
    anomaly_id: uuid.UUID,
) -> AnomalyQueueItemResponse:
    res = repository.get_anomaly_result_by_id(db, anomaly_id)
    if not res:
        raise AppException(code="ANOMALY_RESULT_NOT_FOUND", message=f"Anomaly result '{anomaly_id}' not found.", status_code=404)

    entry = res.entry
    tenant_ctx.validate_tenant_access(entry.restaurant_id)

    task_name = entry.task.template.name if entry and entry.task and entry.task.template else "Task Entry"
    user_name = entry.user.name if entry and entry.user else "Kitchen Staff"

    return AnomalyQueueItemResponse(
        id=res.id,
        entry_id=res.entry_id,
        restaurant_id=entry.restaurant_id,
        task_name=task_name,
        user_name=user_name,
        decision=res.decision,
        ml_score=res.ml_score,
        baseline_score=res.baseline_score,
        reasons_jsonb=res.reasons_jsonb,
        analyzed_at=res.analyzed_at,
    )
