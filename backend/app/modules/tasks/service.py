import uuid
from datetime import date
from sqlalchemy.orm import Session
from app.core.exceptions import AppException
from app.core.tenant import TenantContext
from app.jobs.generate_tasks import generate_tasks_for_restaurant
from app.modules.tasks import repository
from app.modules.tasks.schema import TaskGenerateRequest, TaskGenerateResult, TaskResponse


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
