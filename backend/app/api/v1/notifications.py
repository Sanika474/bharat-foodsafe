import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_tenant_context
from app.core.responses import success_response
from app.core.tenant import TenantContext
from app.modules.outbox import schema, service

router = APIRouter(prefix="/notifications", tags=["Notifications & Outbox"])


@router.get("")
def list_notifications(
    unread_only: bool = Query(default=False),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    tenant_ctx: TenantContext = Depends(get_tenant_context),
):
    items, total = service.list_user_notifications(
        db=db,
        tenant_ctx=tenant_ctx,
        unread_only=unread_only,
        skip=skip,
        limit=limit,
    )
    return success_response(
        data={
            "notifications": [item.model_dump(mode="json") for item in items],
            "total": total,
        }
    )


@router.patch("/{notification_id}/read")
def mark_notification_read(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    tenant_ctx: TenantContext = Depends(get_tenant_context),
):
    item = service.mark_user_notification_read(db=db, tenant_ctx=tenant_ctx, notification_id=notification_id)
    db.commit()
    return success_response(data=item.model_dump(mode="json"))


@router.post("/read-all")
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    tenant_ctx: TenantContext = Depends(get_tenant_context),
):
    count = service.mark_all_user_notifications_read(db=db, tenant_ctx=tenant_ctx)
    db.commit()
    return success_response(data={"marked_read_count": count})


@router.get("/preferences")
def get_notification_preferences(
    db: Session = Depends(get_db),
    tenant_ctx: TenantContext = Depends(get_tenant_context),
):
    prefs = service.get_user_preferences(db=db, tenant_ctx=tenant_ctx)
    return success_response(
        data=[p.model_dump(mode="json") for p in prefs]
    )


@router.put("/preferences")
def update_notification_preference(
    pref_in: schema.NotificationPreferenceUpdate,
    db: Session = Depends(get_db),
    tenant_ctx: TenantContext = Depends(get_tenant_context),
):
    updated = service.update_user_preference(db=db, tenant_ctx=tenant_ctx, preference_in=pref_in)
    db.commit()
    return success_response(data=updated.model_dump(mode="json"))
