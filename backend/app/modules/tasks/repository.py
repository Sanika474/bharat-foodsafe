import uuid
from datetime import date, datetime
from typing import Sequence
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, joinedload
from app.models.tasks_and_rules import Task, TaskAssignment, TaskTemplate, TaskTemplateVersion


def get_task_by_id(db: Session, task_id: uuid.UUID) -> Task | None:
    stmt = (
        select(Task)
        .options(joinedload(Task.assignments))
        .where(Task.id == task_id)
    )
    return db.scalar(stmt)


def get_task_by_template_and_occurrence(
    db: Session,
    template_id: uuid.UUID,
    occurrence_key: str,
) -> Task | None:
    stmt = select(Task).where(
        and_(
            Task.template_id == template_id,
            Task.occurrence_key == occurrence_key,
        )
    )
    return db.scalar(stmt)


def create_task(
    db: Session,
    restaurant_id: uuid.UUID,
    template_id: uuid.UUID,
    template_version_id: uuid.UUID,
    occurrence_key: str,
    due_at: datetime,
    status: str = "PENDING",
) -> Task:
    task = Task(
        id=uuid.uuid4(),
        restaurant_id=restaurant_id,
        template_id=template_id,
        template_version_id=template_version_id,
        occurrence_key=occurrence_key,
        due_at=due_at,
        status=status,
    )
    db.add(task)
    db.flush()
    return task


def create_task_assignment(
    db: Session,
    task_id: uuid.UUID,
    user_id: uuid.UUID,
) -> TaskAssignment:
    assignment = TaskAssignment(
        id=uuid.uuid4(),
        task_id=task_id,
        user_id=user_id,
    )
    db.add(assignment)
    db.flush()
    return assignment


def list_active_templates_for_restaurant(
    db: Session,
    restaurant_id: uuid.UUID,
) -> Sequence[TaskTemplate]:
    stmt = select(TaskTemplate).where(
        and_(
            TaskTemplate.restaurant_id == restaurant_id,
            TaskTemplate.is_active == True,
        )
    )
    return db.scalars(stmt).all()


def list_all_active_templates(db: Session) -> Sequence[TaskTemplate]:
    stmt = select(TaskTemplate).where(TaskTemplate.is_active == True)
    return db.scalars(stmt).all()


def get_latest_template_version(db: Session, template_id: uuid.UUID) -> TaskTemplateVersion | None:
    stmt = (
        select(TaskTemplateVersion)
        .where(TaskTemplateVersion.template_id == template_id)
        .order_by(TaskTemplateVersion.version_number.desc())
        .limit(1)
    )
    return db.scalar(stmt)


def list_tasks(
    db: Session,
    restaurant_id: uuid.UUID | None = None,
    status: str | None = None,
    template_id: uuid.UUID | None = None,
    target_date: date | None = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[Sequence[Task], int]:
    stmt = select(Task).options(joinedload(Task.assignments))
    count_stmt = select(func.count(Task.id))

    filters = []
    if restaurant_id:
        filters.append(Task.restaurant_id == restaurant_id)
    if status:
        filters.append(Task.status == status)
    if template_id:
        filters.append(Task.template_id == template_id)
    if target_date:
        filters.append(func.date(Task.due_at) == target_date)

    if filters:
        stmt = stmt.where(and_(*filters))
        count_stmt = count_stmt.where(and_(*filters))

    total = db.scalar(count_stmt) or 0

    stmt = stmt.order_by(Task.due_at.asc(), Task.created_at.desc()).offset(skip).limit(limit)
    tasks = db.scalars(stmt).unique().all()

    return tasks, total
