import logging
import uuid
from datetime import date, datetime, time, timezone
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.models.tasks_and_rules import TaskTemplate, TaskTemplateVersion
from app.modules.tasks import repository
from app.modules.tasks.schema import TaskGenerateResult

logger = logging.getLogger(__name__)


def compute_occurrence_key(
    template: TaskTemplate,
    version: TaskTemplateVersion,
    target_date: date,
) -> str:
    date_str = target_date.strftime("%Y-%m-%d")
    config = version.configuration_jsonb or {}
    freq = (template.frequency_type or "DAILY").upper()

    if freq == "DAILY":
        base_key = date_str
    elif freq in ("SHIFT_START", "SHIFT_END", "SHIFT"):
        shift_name = config.get("shift_name", freq)
        base_key = f"{date_str}:{shift_name}"
    elif freq == "WEEKLY":
        base_key = f"{date_str}:WEEKLY"
    elif freq == "MONTHLY":
        base_key = target_date.strftime("%Y-%m")
    else:
        base_key = f"{date_str}:{freq}"

    custom_suffix = config.get("occurrence_key_suffix")
    if custom_suffix:
        base_key = f"{base_key}:{custom_suffix}"

    return base_key


def compute_due_at(
    target_date: date,
    version: TaskTemplateVersion,
) -> datetime:
    config = version.configuration_jsonb or {}

    due_time_str = config.get("due_time")
    if due_time_str and isinstance(due_time_str, str):
        try:
            parts = due_time_str.split(":")
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
            return datetime.combine(target_date, time(hour, minute), tzinfo=timezone.utc)
        except Exception:
            pass

    return datetime.combine(target_date, time(23, 59, 59), tzinfo=timezone.utc)


def generate_tasks_for_restaurant(
    db: Session,
    restaurant_id: uuid.UUID,
    target_date: date | None = None,
) -> TaskGenerateResult:
    if target_date is None:
        target_date = datetime.now(timezone.utc).date()

    templates = repository.list_active_templates_for_restaurant(db, restaurant_id)

    created_count = 0
    skipped_count = 0
    task_ids: list[uuid.UUID] = []

    for template in templates:
        version = repository.get_latest_template_version(db, template.id)
        if not version:
            logger.warning(f"Template {template.id} has no versions. Skipping.")
            continue

        occurrence_key = compute_occurrence_key(template, version, target_date)
        due_at = compute_due_at(target_date, version)

        # Idempotency check 1: Check existing in DB
        existing = repository.get_task_by_template_and_occurrence(db, template.id, occurrence_key)
        if existing:
            skipped_count += 1
            task_ids.append(existing.id)
            continue

        # Transaction-safe creation via savepoint
        try:
            with db.begin_nested():
                task = repository.create_task(
                    db=db,
                    restaurant_id=restaurant_id,
                    template_id=template.id,
                    template_version_id=version.id,
                    occurrence_key=occurrence_key,
                    due_at=due_at,
                    status="PENDING",
                )

                config = version.configuration_jsonb or {}
                assigned_users = config.get("assigned_user_ids") or []
                if isinstance(assigned_users, list):
                    for u_id in assigned_users:
                        try:
                            user_uuid = uuid.UUID(str(u_id))
                            repository.create_task_assignment(db, task.id, user_uuid)
                        except (ValueError, TypeError):
                            pass

                created_count += 1
                task_ids.append(task.id)
        except IntegrityError:
            skipped_count += 1
            existing = repository.get_task_by_template_and_occurrence(db, template.id, occurrence_key)
            if existing and existing.id not in task_ids:
                task_ids.append(existing.id)

    db.commit()

    return TaskGenerateResult(
        restaurant_id=restaurant_id,
        target_date=target_date.strftime("%Y-%m-%d"),
        templates_processed=len(templates),
        tasks_created=created_count,
        tasks_skipped_existing=skipped_count,
        task_ids=task_ids,
    )


def generate_tasks_all_restaurants(
    db: Session,
    target_date: date | None = None,
) -> list[TaskGenerateResult]:
    if target_date is None:
        target_date = datetime.now(timezone.utc).date()

    active_templates = repository.list_all_active_templates(db)
    restaurant_ids = {t.restaurant_id for t in active_templates}

    results = []
    for rest_id in restaurant_ids:
        res = generate_tasks_for_restaurant(db, rest_id, target_date)
        results.append(res)
    return results
