import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_tenant_context, require_roles
from app.core.responses import success_response
from app.core.tenant import TenantContext
from app.modules.task_templates import service
from app.modules.task_templates.schema import (
    TaskTemplateCreate,
    TaskTemplateUpdate,
    VersionCreateRequest,
)

router = APIRouter(prefix="/task-templates", tags=["Task Templates"])


@router.post("", status_code=201)
def create_template(
    body: TaskTemplateCreate,
    db: Session = Depends(get_db),
    tenant_ctx: TenantContext = Depends(get_tenant_context),
    _role_guard: tuple = Depends(require_roles("MANAGER", "PLATFORM_ADMIN")),
):
    template_resp = service.create_task_template(db, tenant_ctx, body)
    return success_response(data=template_resp.model_dump(), status_code=201)


@router.get("")
def list_templates(
    category_id: uuid.UUID | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    tenant_ctx: TenantContext = Depends(get_tenant_context),
):
    templates = service.list_task_templates(
        db=db,
        tenant_ctx=tenant_ctx,
        category_id=category_id,
        is_active=is_active,
        skip=skip,
        limit=limit,
    )
    return success_response(data=[t.model_dump() for t in templates])


@router.get("/{template_id}")
def get_template(
    template_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_ctx: TenantContext = Depends(get_tenant_context),
):
    template_resp = service.get_task_template(db, tenant_ctx, template_id)
    return success_response(data=template_resp.model_dump())


@router.put("/{template_id}")
def update_template(
    template_id: uuid.UUID,
    body: TaskTemplateUpdate,
    db: Session = Depends(get_db),
    tenant_ctx: TenantContext = Depends(get_tenant_context),
    _role_guard: tuple = Depends(require_roles("MANAGER", "PLATFORM_ADMIN")),
):
    template_resp = service.update_task_template(db, tenant_ctx, template_id, body)
    return success_response(data=template_resp.model_dump())


@router.post("/{template_id}/versions", status_code=201)
def create_version(
    template_id: uuid.UUID,
    body: VersionCreateRequest,
    db: Session = Depends(get_db),
    tenant_ctx: TenantContext = Depends(get_tenant_context),
    _role_guard: tuple = Depends(require_roles("MANAGER", "PLATFORM_ADMIN")),
):
    version_resp = service.create_template_version(
        db=db,
        tenant_ctx=tenant_ctx,
        template_id=template_id,
        configuration_jsonb=body.configuration_jsonb,
    )
    return success_response(data=version_resp.model_dump(), status_code=201)


@router.get("/{template_id}/versions")
def list_versions(
    template_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_ctx: TenantContext = Depends(get_tenant_context),
):
    versions = service.list_template_versions(db, tenant_ctx, template_id)
    return success_response(data=[v.model_dump() for v in versions])


@router.get("/{template_id}/versions/{version_number}")
def get_version(
    template_id: uuid.UUID,
    version_number: int,
    db: Session = Depends(get_db),
    tenant_ctx: TenantContext = Depends(get_tenant_context),
):
    version_resp = service.get_template_version_by_number(
        db=db,
        tenant_ctx=tenant_ctx,
        template_id=template_id,
        version_number=version_number,
    )
    return success_response(data=version_resp.model_dump())
