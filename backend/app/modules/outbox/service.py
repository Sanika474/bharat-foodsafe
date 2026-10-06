import logging
import uuid
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.core.tenant import TenantContext
from app.models.notifications_and_audit import Notification, NotificationPreference, OutboxEvent
from app.modules.outbox import repository, schema

logger = logging.getLogger(__name__)


def record_outbox_event(
    db: Session,
    event_type: str,
    aggregate_type: str,
    aggregate_id: uuid.UUID,
    payload_jsonb: dict,
    restaurant_id: uuid.UUID | None = None,
    dedupe_key: str | None = None,
) -> OutboxEvent:
    """
    Records an event in the transactional outbox table.
    MUST be called within the same DB transaction as the business operation.
    Does not commit the transaction.
    """
    return repository.create_outbox_event(
        db=db,
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        payload_jsonb=payload_jsonb,
        restaurant_id=restaurant_id,
        dedupe_key=dedupe_key,
    )


def process_single_outbox_event(db: Session, event: OutboxEvent, max_retries: int = 5) -> bool:
    """
    Processes a claimed outbox event.
    Resolves target users, checks notification preferences, creates notifications idempotently,
    and updates outbox event status to PROCESSED or FAILED/PENDING.
    """
    try:
        title = event.payload_jsonb.get("title", f"Alert: {event.event_type}")
        message = event.payload_jsonb.get("message", f"Event {event.event_type} occurred.")

        recipients = repository.get_recipient_users_for_event(
            db=db,
            event_type=event.event_type,
            restaurant_id=event.restaurant_id,
            payload_jsonb=event.payload_jsonb,
        )

        for user in recipients:
            # Check user preferences
            if repository.is_notification_enabled_for_user(
                db=db, user_id=user.id, event_type=event.event_type, channel="IN_APP"
            ):
                repository.create_notification_if_not_exists(
                    db=db,
                    user_id=user.id,
                    outbox_event_id=event.id,
                    title=title,
                    message=message,
                    event_type=event.event_type,
                    restaurant_id=event.restaurant_id,
                )

        # Mark processed
        event.status = "PROCESSED"
        event.lease_id = None
        event.lease_expires_at = None
        event.last_error = None
        return True
    except Exception as e:
        logger.error(f"Error processing outbox event {event.id}: {e}", exc_info=True)
        event.retry_count += 1
        event.last_error = str(e)
        event.lease_id = None
        event.lease_expires_at = None

        if event.retry_count >= max_retries:
            event.status = "FAILED"
        else:
            event.status = "PENDING"
        return False


def process_outbox_batch(
    db: Session,
    worker_id: uuid.UUID | None = None,
    batch_size: int = 10,
    max_retries: int = 5,
) -> tuple[int, int]:
    """
    Runs one batch of outbox event claiming & processing.
    Returns (success_count, failure_count).
    """
    if not worker_id:
        worker_id = uuid.uuid4()

    claimed_events = repository.claim_pending_outbox_events(
        db=db,
        worker_id=worker_id,
        batch_size=batch_size,
    )

    success_count = 0
    failure_count = 0

    for event in claimed_events:
        with db.begin_nested():
            ok = process_single_outbox_event(db=db, event=event, max_retries=max_retries)
            if ok:
                success_count += 1
            else:
                failure_count += 1

    db.commit()
    return success_count, failure_count


def list_user_notifications(
    db: Session,
    tenant_ctx: TenantContext,
    unread_only: bool = False,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[schema.NotificationResponse], int]:
    restaurant_id = None if tenant_ctx.is_platform_admin() else tenant_ctx.restaurant_id
    items, total = repository.get_user_notifications(
        db=db,
        user_id=tenant_ctx.user_id,
        restaurant_id=restaurant_id,
        unread_only=unread_only,
        skip=skip,
        limit=limit,
    )
    dtos = [schema.NotificationResponse.model_validate(n) for n in items]
    return dtos, total


def mark_user_notification_read(
    db: Session,
    tenant_ctx: TenantContext,
    notification_id: uuid.UUID,
) -> schema.NotificationResponse:
    n = repository.mark_notification_read(db=db, notification_id=notification_id, user_id=tenant_ctx.user_id)
    if not n:
        raise AppException(
            code="NOTIFICATION_NOT_FOUND",
            message=f"Notification '{notification_id}' not found.",
            status_code=404,
        )
    return schema.NotificationResponse.model_validate(n)


def mark_all_user_notifications_read(db: Session, tenant_ctx: TenantContext) -> int:
    restaurant_id = None if tenant_ctx.is_platform_admin() else tenant_ctx.restaurant_id
    return repository.mark_all_notifications_read(
        db=db,
        user_id=tenant_ctx.user_id,
        restaurant_id=restaurant_id,
    )


def get_user_preferences(db: Session, tenant_ctx: TenantContext) -> list[schema.NotificationPreferenceResponse]:
    prefs = repository.get_user_notification_preferences(db=db, user_id=tenant_ctx.user_id)
    return [schema.NotificationPreferenceResponse.model_validate(p) for p in prefs]


def update_user_preference(
    db: Session,
    tenant_ctx: TenantContext,
    preference_in: schema.NotificationPreferenceUpdate,
) -> schema.NotificationPreferenceResponse:
    pref = repository.upsert_user_notification_preference(
        db=db,
        user_id=tenant_ctx.user_id,
        channel=preference_in.channel,
        event_type=preference_in.event_type,
        enabled=preference_in.enabled,
    )
    return schema.NotificationPreferenceResponse.model_validate(pref)
