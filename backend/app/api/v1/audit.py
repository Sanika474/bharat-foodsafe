import uuid
from datetime import datetime
from typing import Any
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core import audit
from app.core.deps import get_db, get_tenant_context, require_roles
from app.core.exceptions import AppException
from app.core.responses import success_response
from app.core.tenant import TenantContext

router = APIRouter(prefix="/audit", tags=["Audit Log & Hash Chain Integrity"])


class AuditLogResponse(BaseModel):
    id: uuid.UUID
    restaurant_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    event_name: str
    resource_type: str
    resource_id: uuid.UUID | None = None
    payload_jsonb: Any | None = None
    previous_hash: str | None = None
    record_hash: str
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/logs")
def list_audit_logs(
    event_name: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    resource_id: uuid.UUID | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    tenant_ctx: TenantContext = Depends(get_tenant_context),
    _role_guard: tuple = Depends(require_roles("MANAGER", "PLATFORM_ADMIN")),
):
    target_restaurant_id = None if tenant_ctx.is_platform_admin() else tenant_ctx.restaurant_id
    records, total = audit.list_audit_logs(
        db=db,
        restaurant_id=target_restaurant_id,
        event_name=event_name,
        resource_type=resource_type,
        resource_id=resource_id,
        skip=skip,
        limit=limit,
    )
    res_list = [AuditLogResponse.model_validate(r).model_dump(mode="json") for r in records]
    return success_response(data={"logs": res_list, "total": total})


@router.get("/logs/{audit_id}")
def get_audit_log(
    audit_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_ctx: TenantContext = Depends(get_tenant_context),
    _role_guard: tuple = Depends(require_roles("MANAGER", "PLATFORM_ADMIN")),
):
    record = audit.get_audit_log_by_id(db, audit_id)
    if not record:
        raise AppException(code="AUDIT_LOG_NOT_FOUND", message=f"Audit log entry '{audit_id}' not found.", status_code=404)
    if record.restaurant_id:
        tenant_ctx.validate_tenant_access(record.restaurant_id)
    return success_response(data=AuditLogResponse.model_validate(record).model_dump(mode="json"))


@router.post("/verify")
def verify_audit_chain(
    db: Session = Depends(get_db),
    tenant_ctx: TenantContext = Depends(get_tenant_context),
    _role_guard: tuple = Depends(require_roles("MANAGER", "PLATFORM_ADMIN")),
):
    target_restaurant_id = None if tenant_ctx.is_platform_admin() else tenant_ctx.restaurant_id
    result = audit.verify_audit_chain(db, restaurant_id=target_restaurant_id)
    return success_response(data=result)


@router.put("/logs/{audit_id}")
@router.patch("/logs/{audit_id}")
@router.delete("/logs/{audit_id}")
def prohibit_audit_mutation(
    audit_id: uuid.UUID,
    _tenant_ctx: TenantContext = Depends(get_tenant_context),
):
    """Audit log records are immutable. Returns 409 Conflict / 405 Method Not Allowed."""
    raise AppException(
        code="AUDIT_LOG_IMMUTABLE",
        message="Audit log records are immutable and cannot be updated or deleted.",
        status_code=409,
    )
