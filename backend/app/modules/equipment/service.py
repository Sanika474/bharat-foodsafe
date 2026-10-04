import uuid
from sqlalchemy.orm import Session
from app.core.exceptions import AppException
from app.core.tenant import TenantContext
from app.models.tasks_and_rules import Equipment
from app.modules.equipment import repository
from app.modules.equipment.schema import EquipmentCreate, EquipmentResponse, EquipmentUpdate


def _build_equipment_response(equipment: Equipment) -> EquipmentResponse:
    return EquipmentResponse(
        id=equipment.id,
        restaurant_id=equipment.restaurant_id,
        name=equipment.name,
        equipment_type=equipment.equipment_type,
        location=equipment.location,
        serial_number=equipment.serial_number,
        min_temp=float(equipment.min_temp) if equipment.min_temp is not None else None,
        max_temp=float(equipment.max_temp) if equipment.max_temp is not None else None,
        status=equipment.status,
        created_at=equipment.created_at,
        updated_at=equipment.updated_at,
    )


def create_equipment(
    db: Session,
    tenant_ctx: TenantContext,
    req: EquipmentCreate,
) -> EquipmentResponse:
    target_restaurant_id = req.restaurant_id or tenant_ctx.restaurant_id

    if not target_restaurant_id:
        raise AppException(
            code="TENANT_ID_REQUIRED",
            message="restaurant_id is required to register equipment.",
            status_code=400,
        )

    # Enforce tenant isolation
    tenant_ctx.validate_tenant_access(target_restaurant_id)

    equipment = repository.create_equipment(
        db=db,
        restaurant_id=target_restaurant_id,
        name=req.name,
        equipment_type=req.equipment_type,
        location=req.location,
        serial_number=req.serial_number,
        min_temp=req.min_temp,
        max_temp=req.max_temp,
        status=req.status,
    )

    db.commit()
    db.refresh(equipment)

    return _build_equipment_response(equipment)


def get_equipment(
    db: Session,
    tenant_ctx: TenantContext,
    equipment_id: uuid.UUID,
) -> EquipmentResponse:
    equipment = repository.get_equipment_by_id(db, equipment_id)
    if not equipment:
        raise AppException(
            code="EQUIPMENT_NOT_FOUND",
            message=f"Equipment '{equipment_id}' not found.",
            status_code=404,
        )

    # Enforce tenant isolation
    tenant_ctx.validate_tenant_access(equipment.restaurant_id)

    return _build_equipment_response(equipment)


def update_equipment(
    db: Session,
    tenant_ctx: TenantContext,
    equipment_id: uuid.UUID,
    req: EquipmentUpdate,
) -> EquipmentResponse:
    equipment = repository.get_equipment_by_id(db, equipment_id)
    if not equipment:
        raise AppException(
            code="EQUIPMENT_NOT_FOUND",
            message=f"Equipment '{equipment_id}' not found.",
            status_code=404,
        )

    # Enforce tenant isolation
    tenant_ctx.validate_tenant_access(equipment.restaurant_id)

    # Temperature range check for partial updates
    effective_min = req.min_temp if req.min_temp is not None else equipment.min_temp
    effective_max = req.max_temp if req.max_temp is not None else equipment.max_temp
    if effective_min is not None and effective_max is not None:
        if float(effective_min) > float(effective_max):
            raise AppException(
                code="INVALID_TEMPERATURE_RANGE",
                message="min_temp cannot be greater than max_temp.",
                status_code=422,
            )

    update_dict = req.model_dump(exclude_unset=True)
    updated_equipment = repository.update_equipment(db, equipment, update_dict)

    db.commit()
    db.refresh(updated_equipment)

    return _build_equipment_response(updated_equipment)


def delete_equipment(
    db: Session,
    tenant_ctx: TenantContext,
    equipment_id: uuid.UUID,
) -> None:
    equipment = repository.get_equipment_by_id(db, equipment_id)
    if not equipment:
        raise AppException(
            code="EQUIPMENT_NOT_FOUND",
            message=f"Equipment '{equipment_id}' not found.",
            status_code=404,
        )

    # Enforce tenant isolation
    tenant_ctx.validate_tenant_access(equipment.restaurant_id)

    repository.delete_equipment(db, equipment)
    db.commit()


def list_equipment(
    db: Session,
    tenant_ctx: TenantContext,
    status: str | None = None,
    equipment_type: str | None = None,
    search: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> list[EquipmentResponse]:
    filter_restaurant_id = None if tenant_ctx.is_platform_admin() else tenant_ctx.restaurant_id

    items = repository.list_equipment(
        db=db,
        restaurant_id=filter_restaurant_id,
        status=status,
        equipment_type=equipment_type,
        search=search,
        skip=skip,
        limit=limit,
    )

    return [_build_equipment_response(eq) for eq in items]
