import uuid
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_tenant_context, require_roles
from app.core.responses import success_response
from app.core.tenant import TenantContext
from app.modules.safety_rules import service
from app.modules.safety_rules.schema import StandaloneEvaluateRequest

router = APIRouter(prefix="/safety-rules", tags=["Safety Rules Engine"])


@router.post(
    "/evaluate",
    summary="Evaluate an observation payload against applicable deterministic safety rules without persisting",
)
def evaluate_observation_endpoint(
    req: StandaloneEvaluateRequest,
    db: Session = Depends(get_db),
    tenant_ctx: TenantContext = Depends(get_tenant_context),
    _role_guard: tuple = Depends(require_roles("STAFF", "MANAGER", "PLATFORM_ADMIN")),
):
    result = service.evaluate_standalone(db, tenant_ctx, req)
    return success_response(data=result.model_dump())


@router.get(
    "",
    summary="List active verified safety rules for current outlet scope",
)
def list_safety_rules_endpoint(
    db: Session = Depends(get_db),
    tenant_ctx: TenantContext = Depends(get_tenant_context),
    _role_guard: tuple = Depends(require_roles("STAFF", "MANAGER", "PLATFORM_ADMIN")),
):
    rules = service.list_active_rules(db, tenant_ctx)
    return success_response(data=[r.model_dump() for r in rules])


@router.get(
    "/sources",
    summary="List regulatory rule sources (e.g. FSSAI guidelines)",
)
def list_rule_sources_endpoint(
    db: Session = Depends(get_db),
    tenant_ctx: TenantContext = Depends(get_tenant_context),
    _role_guard: tuple = Depends(require_roles("STAFF", "MANAGER", "PLATFORM_ADMIN")),
):
    sources = service.list_rule_sources(db, tenant_ctx)
    return success_response(data=[s.model_dump() for s in sources])


@router.get(
    "/entries/{entry_id}/evaluations",
    summary="List persisted immutable safety evaluations for a executed task entry",
)
def get_entry_evaluations_endpoint(
    entry_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_ctx: TenantContext = Depends(get_tenant_context),
    _role_guard: tuple = Depends(require_roles("STAFF", "MANAGER", "PLATFORM_ADMIN")),
):
    evals = service.get_entry_evaluations(db, tenant_ctx, entry_id)
    return success_response(data=[e.model_dump() for e in evals])
