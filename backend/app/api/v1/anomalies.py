import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_tenant_context, require_roles
from app.core.responses import success_response
from app.core.tenant import TenantContext
from app.modules.anomaly import repository, service

router = APIRouter(prefix="/anomalies", tags=["Record-Integrity Anomaly Engine"])


@router.get("")
def list_anomalies(
    decision: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    tenant_ctx: TenantContext = Depends(get_tenant_context),
    _role_guard: tuple = Depends(require_roles("MANAGER", "PLATFORM_ADMIN")),
):
    items, total = service.list_anomalies(
        db=db,
        tenant_ctx=tenant_ctx,
        decision=decision,
        skip=skip,
        limit=limit,
    )
    return success_response(
        data={
            "anomalies": [item.model_dump(mode="json") for item in items],
            "total": total,
        }
    )


@router.get("/{anomaly_id}")
def get_anomaly(
    anomaly_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_ctx: TenantContext = Depends(get_tenant_context),
    _role_guard: tuple = Depends(require_roles("MANAGER", "PLATFORM_ADMIN")),
):
    item = service.get_anomaly_by_id(db, tenant_ctx, anomaly_id)
    return success_response(data=item.model_dump(mode="json"))


@router.post("/analyze/{entry_id}")
def analyze_entry_anomaly(
    entry_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_ctx: TenantContext = Depends(get_tenant_context),
    _role_guard: tuple = Depends(require_roles("MANAGER", "PLATFORM_ADMIN")),
):
    from app.models.tasks_and_rules import Entry
    entry = db.query(Entry).filter(Entry.id == entry_id).first()
    if not entry:
        from app.core.exceptions import AppException
        raise AppException(code="ENTRY_NOT_FOUND", message=f"Entry '{entry_id}' not found.", status_code=404)

    tenant_ctx.validate_tenant_access(entry.restaurant_id)

    res = service.evaluate_entry_anomaly(db, entry, user_id=tenant_ctx.user_id)
    db.commit()

    item = service.get_anomaly_by_id(db, tenant_ctx, res.id)
    return success_response(data=item.model_dump(mode="json"))
