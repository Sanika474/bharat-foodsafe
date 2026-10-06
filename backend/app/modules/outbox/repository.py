import uuid
from datetime import datetime, timedelta, timezone
from typing import Sequence
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.models.identity import Role, User, UserRole
from app.models.notifications_and_audit import Notification, NotificationPreference, OutboxEvent


def create_outbox_event(
    db: Session,
    event_type: str,
    aggregate_type: str,
    aggregate_id: uuid.UUID,
    payload_jsonb: dict,
    restaurant_id: uuid.UUID | None = None,
    dedupe_key: str | None = None,
) -> OutboxEvent:
    """
    Creates an outbox event within caller's active database transaction.
    Atomically committed with originating business mutation.
    """
    if dedupe_key:
        existing = db.scalar(select(OutboxEvent).where(OutboxEvent.dedupe_key == dedupe_key))
        if existing:
            return existing

    outbox_event = OutboxEvent(
        id=uuid.uuid4(),
        restaurant_id=restaurant_id,
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        payload_jsonb=payload_jsonb,
        status="PENDING",
        retry_count=0,
        dedupe_key=dedupe_key,
    )
    db.add(outbox_event)
    return outbox_event


def claim_pending_outbox_events(
    db: Session,
    worker_id: uuid.UUID,
    batch_size: int = 10,
    lease_duration_seconds: int = 60,
) -> list[OutboxEvent]:
    """
    Claims pending or expired-lease outbox events using FOR UPDATE SKIP LOCKED.
    Safely handles concurrent worker instances.
    """
    now = datetime.now(timezone.utc)
    stmt = (
        select(OutboxEvent)
        .where(
            or_(
                OutboxEvent.status == "PENDING",
                and_(
                    OutboxEvent.status == "PROCESSING",
                    OutboxEvent.lease_expires_at < now,
                ),
            )
        )
        .order_by(OutboxEvent.created_at.asc())
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    )

    events = list(db.scalars(stmt).all())
    expires_at = now + timedelta(seconds=lease_duration_seconds)

    for event in events:
        event.status = "PROCESSING"
        event.lease_id = worker_id
        event.lease_expires_at = expires_at

    db.flush()
    return events


def get_recipient_users_for_event(
    db: Session,
    event_type: str,
    restaurant_id: uuid.UUID | None,
    payload_jsonb: dict,
) -> list[User]:
    """
    Resolves recipient users based on event_type, tenant restaurant_id, and payload context.
    """
    if not restaurant_id:
        return []

    # Get manager role IDs
    manager_roles = db.scalars(
        select(Role.id).where(Role.name.in_(["MANAGER", "RESTAURANT_ADMIN", "PLATFORM_ADMIN"]))
    ).all()

    # Base query for managers of the restaurant
    mgr_user_ids = db.scalars(
        select(UserRole.user_id)
        .where(
            UserRole.restaurant_id == restaurant_id,
            UserRole.role_id.in_(manager_roles),
        )
    ).all()

    target_user_ids = set(mgr_user_ids)

    # Specific event handling
    if event_type == "CAPA_ASSIGNED":
        assigned_to_str = payload_jsonb.get("assigned_to")
        if assigned_to_str:
            try:
                target_user_ids.add(uuid.UUID(assigned_to_str))
            except ValueError:
                pass

    if event_type in ("TASK_COMPLETED", "TASK_OVERDUE"):
        user_id_str = payload_jsonb.get("user_id")
        if user_id_str:
            try:
                target_user_ids.add(uuid.UUID(user_id_str))
            except ValueError:
                pass

    if not target_user_ids:
        return []

    users = list(db.scalars(
        select(User).where(User.id.in_(list(target_user_ids)), User.status == "ACTIVE")
    ).all())
    return users


def is_notification_enabled_for_user(
    db: Session,
    user_id: uuid.UUID,
    event_type: str,
    channel: str = "IN_APP",
) -> bool:
    """
    Checks if a user has enabled a notification preference for given channel & event_type.
    Default is True if no explicit preference record exists.
    """
    pref = db.scalar(
        select(NotificationPreference).where(
            NotificationPreference.user_id == user_id,
            NotificationPreference.channel == channel,
            NotificationPreference.event_type == event_type,
        )
    )
    if pref is not None:
        return pref.enabled
    return True


def create_notification_if_not_exists(
    db: Session,
    user_id: uuid.UUID,
    outbox_event_id: uuid.UUID,
    title: str,
    message: str,
    event_type: str,
    restaurant_id: uuid.UUID | None = None,
) -> Notification | None:
    """
    Idempotently creates a notification for a user linked to an outbox_event_id.
    """
    existing = db.scalar(
        select(Notification).where(
            Notification.user_id == user_id,
            Notification.outbox_event_id == outbox_event_id,
        )
    )
    if existing:
        return existing

    notification = Notification(
        id=uuid.uuid4(),
        restaurant_id=restaurant_id,
        user_id=user_id,
        outbox_event_id=outbox_event_id,
        title=title,
        message=message,
        event_type=event_type,
    )
    db.add(notification)
    return notification


def get_user_notifications(
    db: Session,
    user_id: uuid.UUID,
    restaurant_id: uuid.UUID | None = None,
    unread_only: bool = False,
    skip: int = 0,
    limit: int = 50,
) -> tuple[Sequence[Notification], int]:
    stmt = select(Notification).where(Notification.user_id == user_id)
    count_stmt = select(func.count(Notification.id)).where(Notification.user_id == user_id)

    filters = []
    if restaurant_id:
        filters.append(Notification.restaurant_id == restaurant_id)
    if unread_only:
        filters.append(Notification.read_at.is_(None))

    if filters:
        stmt = stmt.where(and_(*filters))
        count_stmt = count_stmt.where(and_(*filters))

    total = db.scalar(count_stmt) or 0
    stmt = stmt.order_by(Notification.created_at.desc()).offset(skip).limit(limit)
    items = db.scalars(stmt).all()
    return items, total


def mark_notification_read(db: Session, notification_id: uuid.UUID, user_id: uuid.UUID) -> Notification | None:
    stmt = select(Notification).where(Notification.id == notification_id, Notification.user_id == user_id)
    n = db.scalar(stmt)
    if n:
        n.read_at = datetime.now(timezone.utc)
        db.flush()
    return n


def mark_all_notifications_read(db: Session, user_id: uuid.UUID, restaurant_id: uuid.UUID | None = None) -> int:
    stmt = select(Notification).where(Notification.user_id == user_id, Notification.read_at.is_(None))
    if restaurant_id:
        stmt = stmt.where(Notification.restaurant_id == restaurant_id)
    notifications = db.scalars(stmt).all()
    now = datetime.now(timezone.utc)
    count = len(notifications)
    for n in notifications:
        n.read_at = now
    db.flush()
    return count


def get_user_notification_preferences(db: Session, user_id: uuid.UUID) -> Sequence[NotificationPreference]:
    stmt = select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    return db.scalars(stmt).all()


def upsert_user_notification_preference(
    db: Session,
    user_id: uuid.UUID,
    channel: str,
    event_type: str,
    enabled: bool,
) -> NotificationPreference:
    pref = db.scalar(
        select(NotificationPreference).where(
            NotificationPreference.user_id == user_id,
            NotificationPreference.channel == channel,
            NotificationPreference.event_type == event_type,
        )
    )
    if not pref:
        pref = NotificationPreference(
            id=uuid.uuid4(),
            user_id=user_id,
            channel=channel,
            event_type=event_type,
            enabled=enabled,
        )
        db.add(pref)
    else:
        pref.enabled = enabled
    db.flush()
    return pref
