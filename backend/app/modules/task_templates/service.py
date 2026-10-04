import uuid
from sqlalchemy.orm import Session
from app.core.exceptions import AppException
from app.core.tenant import TenantContext
from app.models.tasks_and_rules import TaskTemplate, TaskTemplateVersion
from app.modules.task_templates import repository
from app.modules.task_templates.schema import (
    TaskTemplateCreate,
    TaskTemplateResponse,
    TaskTemplateUpdate,
    TaskTemplateVersionResponse,
)


def _build_template_response(db: Session, template: TaskTemplate) -> TaskTemplateResponse:
    latest_version = repository.get_latest_version(db, template.id)
    latest_ver_num = latest_version.version_number if latest_version else 0

    latest_ver_resp = (
        TaskTemplateVersionResponse.model_validate(latest_version) if latest_version else None
    )

    return TaskTemplateResponse(
        id=template.id,
        restaurant_id=template.restaurant_id,
        category_id=template.category_id,
        name=template.name,
        code=template.code,
        description=template.description,
        frequency_type=template.frequency_type,
        is_active=template.is_active,
        latest_version_number=latest_ver_num,
        latest_version=latest_ver_resp,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


def create_task_template(
    db: Session,
    tenant_ctx: TenantContext,
    req: TaskTemplateCreate,
) -> TaskTemplateResponse:
    # Resolve target restaurant_id
    target_restaurant_id = req.restaurant_id or tenant_ctx.restaurant_id

    if not target_restaurant_id:
        raise AppException(
            code="TENANT_ID_REQUIRED",
            message="restaurant_id is required to create a task template.",
            status_code=400,
        )

    # Enforce tenant isolation
    tenant_ctx.validate_tenant_access(target_restaurant_id)

    # Verify category exists
    category = repository.get_category_by_id(db, req.category_id)
    if not category:
        raise AppException(
            code="CATEGORY_NOT_FOUND",
            message=f"Task category '{req.category_id}' not found.",
            status_code=404,
        )

    # Verify unique code per outlet
    existing = repository.get_template_by_code(db, target_restaurant_id, req.code)
    if existing:
        raise AppException(
            code="DUPLICATE_TEMPLATE_CODE",
            message=f"Template code '{req.code}' already exists for this restaurant outlet.",
            status_code=409,
        )

    # 1. Create parent TaskTemplate
    template = repository.create_template(
        db=db,
        restaurant_id=target_restaurant_id,
        category_id=req.category_id,
        name=req.name,
        code=req.code,
        description=req.description,
        frequency_type=req.frequency_type,
    )

    # 2. Create initial Version #1 (Immutable)
    repository.create_template_version(
        db=db,
        template_id=template.id,
        version_number=1,
        configuration_jsonb=req.configuration_jsonb,
        created_by=tenant_ctx.user_id,
    )

    db.commit()
    db.refresh(template)

    return _build_template_response(db, template)


def get_task_template(
    db: Session,
    tenant_ctx: TenantContext,
    template_id: uuid.UUID,
) -> TaskTemplateResponse:
    template = repository.get_template_by_id(db, template_id)
    if not template:
        raise AppException(
            code="TEMPLATE_NOT_FOUND",
            message=f"Task template '{template_id}' not found.",
            status_code=404,
        )

    # Enforce tenant isolation
    tenant_ctx.validate_tenant_access(template.restaurant_id)

    return _build_template_response(db, template)


def update_task_template(
    db: Session,
    tenant_ctx: TenantContext,
    template_id: uuid.UUID,
    req: TaskTemplateUpdate,
) -> TaskTemplateResponse:
    template = repository.get_template_by_id(db, template_id)
    if not template:
        raise AppException(
            code="TEMPLATE_NOT_FOUND",
            message=f"Task template '{template_id}' not found.",
            status_code=404,
        )

    # Enforce tenant isolation
    tenant_ctx.validate_tenant_access(template.restaurant_id)

    # Update top-level fields
    if req.name is not None:
        template.name = req.name
    if req.description is not None:
        template.description = req.description
    if req.frequency_type is not None:
        template.frequency_type = req.frequency_type
    if req.is_active is not None:
        template.is_active = req.is_active

    # IMMUTABLE VERSIONING: If configuration_jsonb is supplied, append new version (version_number + 1)
    if req.configuration_jsonb is not None:
        latest_ver = repository.get_latest_version(db, template.id)
        next_ver_num = (latest_ver.version_number + 1) if latest_ver else 1

        repository.create_template_version(
            db=db,
            template_id=template.id,
            version_number=next_ver_num,
            configuration_jsonb=req.configuration_jsonb,
            created_by=tenant_ctx.user_id,
        )

    db.commit()
    db.refresh(template)

    return _build_template_response(db, template)


def create_template_version(
    db: Session,
    tenant_ctx: TenantContext,
    template_id: uuid.UUID,
    configuration_jsonb: dict,
) -> TaskTemplateVersionResponse:
    template = repository.get_template_by_id(db, template_id)
    if not template:
        raise AppException(
            code="TEMPLATE_NOT_FOUND",
            message=f"Task template '{template_id}' not found.",
            status_code=404,
        )

    # Enforce tenant isolation
    tenant_ctx.validate_tenant_access(template.restaurant_id)

    latest_ver = repository.get_latest_version(db, template.id)
    next_ver_num = (latest_ver.version_number + 1) if latest_ver else 1

    # IMMUTABLE VERSION CREATION
    new_version = repository.create_template_version(
        db=db,
        template_id=template.id,
        version_number=next_ver_num,
        configuration_jsonb=configuration_jsonb,
        created_by=tenant_ctx.user_id,
    )

    db.commit()
    db.refresh(new_version)

    return TaskTemplateVersionResponse.model_validate(new_version)


def list_task_templates(
    db: Session,
    tenant_ctx: TenantContext,
    category_id: uuid.UUID | None = None,
    is_active: bool | None = None,
    skip: int = 0,
    limit: int = 50,
) -> list[TaskTemplateResponse]:
    # Restrict to tenant's restaurant_id unless PLATFORM_ADMIN
    filter_restaurant_id = None if tenant_ctx.is_platform_admin() else tenant_ctx.restaurant_id

    templates = repository.list_templates(
        db=db,
        restaurant_id=filter_restaurant_id,
        category_id=category_id,
        is_active=is_active,
        skip=skip,
        limit=limit,
    )

    return [_build_template_response(db, t) for t in templates]


def list_template_versions(
    db: Session,
    tenant_ctx: TenantContext,
    template_id: uuid.UUID,
) -> list[TaskTemplateVersionResponse]:
    template = repository.get_template_by_id(db, template_id)
    if not template:
        raise AppException(
            code="TEMPLATE_NOT_FOUND",
            message=f"Task template '{template_id}' not found.",
            status_code=404,
        )

    tenant_ctx.validate_tenant_access(template.restaurant_id)

    versions = repository.list_template_versions(db, template.id)
    return [TaskTemplateVersionResponse.model_validate(v) for v in versions]


def get_template_version_by_number(
    db: Session,
    tenant_ctx: TenantContext,
    template_id: uuid.UUID,
    version_number: int,
) -> TaskTemplateVersionResponse:
    template = repository.get_template_by_id(db, template_id)
    if not template:
        raise AppException(
            code="TEMPLATE_NOT_FOUND",
            message=f"Task template '{template_id}' not found.",
            status_code=404,
        )

    tenant_ctx.validate_tenant_access(template.restaurant_id)

    version = repository.get_version_by_number(db, template.id, version_number)
    if not version:
        raise AppException(
            code="VERSION_NOT_FOUND",
            message=f"Version {version_number} for template '{template_id}' not found.",
            status_code=404,
        )

    return TaskTemplateVersionResponse.model_validate(version)
