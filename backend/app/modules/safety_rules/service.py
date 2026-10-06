import uuid
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.core.tenant import TenantContext
from app.modules.safety_rules import engine, repository
from app.modules.safety_rules.schema import (
    EntryEvaluationResponse,
    RuleEvaluationResult,
    RuleSourceResponse,
    SafetyRuleResponse,
    StandaloneEvaluateRequest,
)


def evaluate_standalone(
    db: Session,
    tenant_ctx: TenantContext,
    req: StandaloneEvaluateRequest,
) -> RuleEvaluationResult:
    """
    Evaluates observation against bound safety rules without saving to DB.
    Useful for client preview / validation testing.
    """
    template_id = req.template_id
    category_id = req.category_id

    # If task_id provided, resolve template & category IDs from task
    if req.task_id:
        from app.modules.tasks import repository as task_repo
        task = task_repo.get_task_by_id(db, req.task_id)
        if not task:
            raise AppException(
                code="TASK_NOT_FOUND",
                message=f"Task '{req.task_id}' not found.",
                status_code=404,
            )
        tenant_ctx.validate_tenant_access(task.restaurant_id)
        template_id = task.template_id
        category_id = task.template.category_id if task.template else None

    rules = repository.get_applicable_rules(
        db=db,
        template_id=template_id,
        category_id=category_id,
        restaurant_id=tenant_ctx.restaurant_id,
    )

    return engine.evaluate_rules_set(
        rules=rules,
        value_numeric=req.value_numeric,
        value_text=req.value_text,
        value_jsonb=req.value_jsonb,
        unit=req.unit,
    )


def list_active_rules(
    db: Session,
    tenant_ctx: TenantContext,
) -> list[SafetyRuleResponse]:
    rules = repository.list_active_rules(db, restaurant_id=tenant_ctx.restaurant_id)
    out = []
    for r in rules:
        resp = SafetyRuleResponse.model_validate(r)
        if r.rule_source:
            resp.source_code = r.rule_source.source_code
            resp.source_title = r.rule_source.title
        out.append(resp)
    return out


def list_rule_sources(
    db: Session,
    tenant_ctx: TenantContext,
) -> list[RuleSourceResponse]:
    sources = repository.list_rule_sources(db)
    return [RuleSourceResponse.model_validate(s) for s in sources]


def get_entry_evaluations(
    db: Session,
    tenant_ctx: TenantContext,
    entry_id: uuid.UUID,
) -> list[EntryEvaluationResponse]:
    from sqlalchemy import select
    from app.models.tasks_and_rules import Entry
    entry = db.scalar(select(Entry).where(Entry.id == entry_id))
    if not entry:
        raise AppException(
            code="ENTRY_NOT_FOUND",
            message=f"Entry '{entry_id}' not found.",
            status_code=404,
        )
    tenant_ctx.validate_tenant_access(entry.restaurant_id)

    evals = repository.get_evaluations_by_entry_id(db, entry_id)
    return [EntryEvaluationResponse.model_validate(e) for e in evals]
