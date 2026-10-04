import uuid
from decimal import Decimal
from typing import Sequence
from sqlalchemy import desc, func
from sqlalchemy.orm import Session
from app.models.tasks_and_rules import Equipment


def create_equipment(
    db: Session,
    restaurant_id: uuid.UUID,
    name: str,
    equipment_type: str,
    location: str | None = None,
    serial_number: str | None = None,
    min_temp: Decimal | float | None = None,
    max_temp: Decimal | float | None = None,
    status: str = "OPERATIONAL",
) -> Equipment:
    eq = Equipment(
        id=uuid.uuid4(),
        restaurant_id=restaurant_id,
        name=name,
        equipment_type=equipment_type,
        location=location,
        serial_number=serial_number,
        min_temp=Decimal(str(min_temp)) if min_temp is not None else None,
        max_temp=Decimal(str(max_temp)) if max_temp is not None else None,
        status=status,
    )
    db.add(eq)
    db.flush()
    return eq


def get_equipment_by_id(
    db: Session,
    equipment_id: uuid.UUID,
    restaurant_id: uuid.UUID | None = None,
) -> Equipment | None:
    query = db.query(Equipment).filter(Equipment.id == equipment_id)
    if restaurant_id:
        query = query.filter(Equipment.restaurant_id == restaurant_id)
    return query.first()


def list_equipment(
    db: Session,
    restaurant_id: uuid.UUID | None = None,
    status: str | None = None,
    equipment_type: str | None = None,
    search: str | None = None,
    skip: int = 0,
    limit: int = 50,
) -> Sequence[Equipment]:
    query = db.query(Equipment)
    if restaurant_id:
        query = query.filter(Equipment.restaurant_id == restaurant_id)
    if status:
        query = query.filter(Equipment.status == status)
    if equipment_type:
        query = query.filter(Equipment.equipment_type == equipment_type)
    if search:
        search_pattern = f"%{search.strip()}%"
        query = query.filter(
            func.lower(Equipment.name).like(func.lower(search_pattern))
            | func.lower(Equipment.serial_number).like(func.lower(search_pattern))
            | func.lower(Equipment.location).like(func.lower(search_pattern))
        )

    return query.order_by(desc(Equipment.created_at)).offset(skip).limit(limit).all()


def update_equipment(
    db: Session,
    equipment: Equipment,
    update_data: dict,
) -> Equipment:
    for field, val in update_data.items():
        if val is not None:
            if field in ("min_temp", "max_temp"):
                val = Decimal(str(val)) if val is not None else None
            setattr(equipment, field, val)
    db.flush()
    return equipment


def delete_equipment(db: Session, equipment: Equipment) -> None:
    db.delete(equipment)
    db.flush()
