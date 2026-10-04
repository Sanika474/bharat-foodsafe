import uuid
from typing import Sequence
from sqlalchemy import desc
from sqlalchemy.orm import Session
from app.models.tasks_and_rules import TaskCategory, TaskTemplate, TaskTemplateVersion


def get_category_by_id(db: Session, category_id: uuid.UUID) -> TaskCategory | None:
    return db.query(TaskCategory).filter(TaskCategory.id == category_id).first()


def get_template_by_id(db: Session, template_id: uuid.UUID, restaurant_id: uuid.UUID | None = None) -> TaskTemplate | None:
    query = db.query(TaskTemplate).filter(TaskTemplate.id == template_id)
    if restaurant_id:
        query = query.filter(TaskTemplate.restaurant_id == restaurant_id)
    return query.first()


def get_template_by_code(db: Session, restaurant_id: uuid.UUID, code: str) -> TaskTemplate | None:
    return (
        db.query(TaskTemplate)
        .filter(TaskTemplate.restaurant_id == restaurant_id, TaskTemplate.code == code)
        .first()
    )


def create_template(
    db: Session,
    restaurant_id: uuid.UUID,
    category_id: uuid.UUID,
    name: str,
    code: str,
    description: str | None = None,
    frequency_type: str = "DAILY",
) -> TaskTemplate:
    template = TaskTemplate(
        id=uuid.uuid4(),
        restaurant_id=restaurant_id,
        category_id=category_id,
        name=name,
        code=code,
        description=description,
        frequency_type=frequency_type,
        is_active=True,
    )
    db.add(template)
    db.flush()
    return template


def create_template_version(
    db: Session,
    template_id: uuid.UUID,
    version_number: int,
    configuration_jsonb: dict,
    created_by: uuid.UUID | None = None,
) -> TaskTemplateVersion:
    version = TaskTemplateVersion(
        id=uuid.uuid4(),
        template_id=template_id,
        version_number=version_number,
        configuration_jsonb=configuration_jsonb,
        created_by=created_by,
    )
    db.add(version)
    db.flush()
    return version


def get_latest_version(db: Session, template_id: uuid.UUID) -> TaskTemplateVersion | None:
    return (
        db.query(TaskTemplateVersion)
        .filter(TaskTemplateVersion.template_id == template_id)
        .order_by(desc(TaskTemplateVersion.version_number))
        .first()
    )


def get_version_by_number(db: Session, template_id: uuid.UUID, version_number: int) -> TaskTemplateVersion | None:
    return (
        db.query(TaskTemplateVersion)
        .filter(
            TaskTemplateVersion.template_id == template_id,
            TaskTemplateVersion.version_number == version_number,
        )
        .first()
    )


def list_templates(
    db: Session,
    restaurant_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    is_active: bool | None = None,
    skip: int = 0,
    limit: int = 50,
) -> Sequence[TaskTemplate]:
    query = db.query(TaskTemplate)
    if restaurant_id:
        query = query.filter(TaskTemplate.restaurant_id == restaurant_id)
    if category_id:
        query = query.filter(TaskTemplate.category_id == category_id)
    if is_active is not None:
        query = query.filter(TaskTemplate.is_active == is_active)

    return query.order_by(desc(TaskTemplate.created_at)).offset(skip).limit(limit).all()


def list_template_versions(db: Session, template_id: uuid.UUID) -> Sequence[TaskTemplateVersion]:
    return (
        db.query(TaskTemplateVersion)
        .filter(TaskTemplateVersion.template_id == template_id)
        .order_by(TaskTemplateVersion.version_number.asc())
        .all()
    )
