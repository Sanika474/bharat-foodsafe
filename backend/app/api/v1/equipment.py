import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_tenant_context, require_roles
from app.core.responses import success_response
from app.core.tenant import TenantContext
from app.modules.equipment import service
from app.modules.equipment.schema import EquipmentCreate, EquipmentUpdate

router = APIRouter(prefix="/equipment", tags=["Equipment Master"])


@router.post("", status_code=201)
def create_equipment(
    body: EquipmentCreate,
    db: Session = Depends(get_db),
    tenant_ctx: TenantContext = Depends(get_tenant_context),
    _role_guard: tuple = Depends(require_roles("MANAGER", "PLATFORM_ADMIN")),
):
    resp = service.create_equipment(db, tenant_ctx, body)
    return success_response(data=resp.model_dump(), status_code=201)


@router.get("")
def list_equipment(
    status: str | None = Query(default=None),
    equipment_type: str | None = Query(default=None),
    search: str | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    tenant_ctx: TenantContext = Depends(get_tenant_context),
):
    items = service.list_equipment(
        db=db,
        tenant_ctx=tenant_ctx,
        status=status,
        equipment_type=equipment_type,
        search=search,
        skip=skip,
        limit=limit,
    )
    return success_response(data=[eq.model_dump() for eq in items])


@router.get("/{equipment_id}")
def get_equipment(
    equipment_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_ctx: TenantContext = Depends(get_tenant_context),
):
    resp = service.get_equipment(db, tenant_ctx, equipment_id)
    return success_response(data=resp.model_dump())


@router.put("/{equipment_id}")
def update_equipment(
    equipment_id: uuid.UUID,
    body: EquipmentUpdate,
    db: Session = Depends(get_db),
    tenant_ctx: TenantContext = Depends(get_tenant_context),
    _role_guard: tuple = Depends(require_roles("MANAGER", "PLATFORM_ADMIN")),
):
    resp = service.update_equipment(db, tenant_ctx, equipment_id, body)
    return success_response(data=resp.model_dump())


@router.delete("/{equipment_id}")
def delete_equipment(
    equipment_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_ctx: TenantContext = Depends(get_tenant_context),
    _role_guard: tuple = Depends(require_roles("MANAGER", "PLATFORM_ADMIN")),
):
    service.delete_equipment(db, tenant_ctx, equipment_id)
    return success_response(data={"message": "Equipment deleted successfully."})
