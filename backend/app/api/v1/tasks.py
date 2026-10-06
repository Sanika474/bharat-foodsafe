import uuid
from datetime import date
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_tenant_context, require_roles
from app.core.responses import success_response
from app.core.tenant import TenantContext
from app.modules.tasks import service
from app.modules.tasks.schema import TaskGenerateRequest

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.post(
    "/generate",
    summary="Trigger idempotent recurring task generation for a restaurant outlet",
)
def generate_tasks_endpoint(
    req: TaskGenerateRequest,
    db: Session = Depends(get_db),
    tenant_ctx: TenantContext = Depends(get_tenant_context),
    _role_guard: tuple = Depends(require_roles("MANAGER", "PLATFORM_ADMIN")),
):
    result = service.generate_scheduled_tasks(db, tenant_ctx, req)
    return success_response(
        data=result.model_dump(),
        meta={"message": f"Generated {result.tasks_created} new tasks, skipped {result.tasks_skipped_existing} existing."},
        status_code=status.HTTP_201_CREATED,
    )


@router.get(
    "",
    summary="List tasks for current outlet with filtering and pagination",
)
def list_tasks_endpoint(
    task_status: str | None = Query(None, alias="status", description="Filter by status (PENDING, IN_PROGRESS, COMPLETED, OVERDUE, MISSED)"),
    template_id: uuid.UUID | None = Query(None, description="Filter by parent template ID"),
    target_date: date | None = Query(None, description="Filter by target due date (YYYY-MM-DD)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    tenant_ctx: TenantContext = Depends(get_tenant_context),
    _role_guard: tuple = Depends(require_roles("STAFF", "MANAGER", "PLATFORM_ADMIN")),
):
    tasks, total = service.list_tasks(
        db=db,
        tenant_ctx=tenant_ctx,
        status=task_status,
        template_id=template_id,
        target_date=target_date,
        skip=skip,
        limit=limit,
    )

    data = [t.model_dump() for t in tasks]
    meta = {
        "pagination": {
            "skip": skip,
            "limit": limit,
            "total": total,
        }
    }
    return success_response(data=data, meta=meta)


@router.get(
    "/{task_id}",
    summary="Get single task instance details",
)
def get_task_endpoint(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_ctx: TenantContext = Depends(get_tenant_context),
    _role_guard: tuple = Depends(require_roles("STAFF", "MANAGER", "PLATFORM_ADMIN")),
):
    task = service.get_task_by_id(db, tenant_ctx, task_id)
    return success_response(data=task.model_dump())
