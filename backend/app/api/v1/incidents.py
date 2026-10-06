import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_tenant_context, require_roles
from app.core.responses import success_response
from app.core.tenant import TenantContext
from app.modules.incidents import service
from app.modules.incidents.schema import (
    AssignCAPARequest,
    CompleteCAPARequest,
    DirectStatusPatchRequest,
    VerifyCAPARequest,
)

router = APIRouter(tags=["Incidents & CAPA Resolution"])


@router.get("/incidents")
def list_incidents(
    status: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    tenant_ctx: TenantContext = Depends(get_tenant_context),
):
    incidents, total = service.list_incidents(
        db=db,
        tenant_ctx=tenant_ctx,
        status=status,
        severity=severity,
        skip=skip,
        limit=limit,
    )
    return success_response(
        data={
            "incidents": [inc.model_dump(mode="json") for inc in incidents],
            "total": total,
        }
    )


@router.get("/incidents/{incident_id}")
def get_incident(
    incident_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_ctx: TenantContext = Depends(get_tenant_context),
):
    incident = service.get_incident_by_id(db, tenant_ctx, incident_id)
    return success_response(data=incident.model_dump(mode="json"))


@router.post("/incidents/{incident_id}/start")
def start_incident(
    incident_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_ctx: TenantContext = Depends(get_tenant_context),
):
    incident = service.start_incident(db, tenant_ctx, incident_id)
    return success_response(data=incident.model_dump(mode="json"))


@router.patch("/incidents/{incident_id}")
def patch_incident(
    incident_id: uuid.UUID,
    _body: DirectStatusPatchRequest,
    _tenant_ctx: TenantContext = Depends(get_tenant_context),
):
    """Direct status mutation is prohibited (Requirement E3.1). Returns 409 Conflict."""
    service.prohibit_direct_status_patch()


@router.get("/corrective-actions")
def list_corrective_actions(
    status: str | None = Query(default=None),
    assigned_to: uuid.UUID | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    tenant_ctx: TenantContext = Depends(get_tenant_context),
):
    cas, total = service.list_corrective_actions(
        db=db,
        tenant_ctx=tenant_ctx,
        status=status,
        assigned_to=assigned_to,
        skip=skip,
        limit=limit,
    )
    return success_response(
        data={
            "corrective_actions": [ca.model_dump(mode="json") for ca in cas],
            "total": total,
        }
    )


@router.get("/corrective-actions/{ca_id}")
def get_corrective_action(
    ca_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_ctx: TenantContext = Depends(get_tenant_context),
):
    ca = service.get_corrective_action_by_id(db, tenant_ctx, ca_id)
    return success_response(data=ca.model_dump(mode="json"))


@router.post("/corrective-actions/{ca_id}/assign")
def assign_corrective_action(
    ca_id: uuid.UUID,
    body: AssignCAPARequest,
    db: Session = Depends(get_db),
    tenant_ctx: TenantContext = Depends(get_tenant_context),
    _role_guard: tuple = Depends(require_roles("MANAGER", "PLATFORM_ADMIN")),
):
    ca = service.assign_corrective_action(db, tenant_ctx, ca_id, body)
    return success_response(data=ca.model_dump(mode="json"))


@router.post("/corrective-actions/{ca_id}/complete")
def complete_corrective_action(
    ca_id: uuid.UUID,
    body: CompleteCAPARequest,
    db: Session = Depends(get_db),
    tenant_ctx: TenantContext = Depends(get_tenant_context),
):
    ca = service.complete_corrective_action_recheck(db, tenant_ctx, ca_id, body)
    return success_response(data=ca.model_dump(mode="json"))


@router.post("/corrective-actions/{ca_id}/verify")
def verify_corrective_action(
    ca_id: uuid.UUID,
    body: VerifyCAPARequest,
    db: Session = Depends(get_db),
    tenant_ctx: TenantContext = Depends(get_tenant_context),
    _role_guard: tuple = Depends(require_roles("MANAGER", "PLATFORM_ADMIN")),
):
    ca = service.verify_corrective_action(db, tenant_ctx, ca_id, body)
    return success_response(data=ca.model_dump(mode="json"))


@router.patch("/corrective-actions/{ca_id}")
def patch_corrective_action(
    ca_id: uuid.UUID,
    _body: DirectStatusPatchRequest,
    _tenant_ctx: TenantContext = Depends(get_tenant_context),
):
    """Direct status mutation is prohibited (Requirement E3.1). Returns 409 Conflict."""
    service.prohibit_direct_status_patch()
