from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select, func, update, desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.notification import Notification
from app.schemas.notification import (
    NotificationResponse,
    UnreadCountResponse,
    NotificationListResponse,
)
from app.auth.dependencies import get_current_user, get_user_record
from app.errors import AppException

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=NotificationListResponse)
def list_notifications(
    unread_only: bool = Query(False, description="Filter for unread notifications only"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List notifications with read/unread state and pagination (FR-080)."""
    stmt = (
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(desc(Notification.created_at))
    )
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))

    total = db.scalar(
        select(func.count(Notification.id)).where(Notification.user_id == current_user.id)
    ) or 0

    unread_count = db.scalar(
        select(func.count(Notification.id)).where(
            Notification.user_id == current_user.id, Notification.is_read.is_(False)
        )
    ) or 0

    items = db.scalars(stmt.offset(offset).limit(limit)).all()

    return NotificationListResponse(
        items=[NotificationResponse.model_validate(n) for n in items],
        total=total,
        unread_count=unread_count,
    )


@router.get("/unread-count", response_model=UnreadCountResponse)
def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the current count of unread notifications for polling (FR-082)."""
    count = db.scalar(
        select(func.count(Notification.id)).where(
            Notification.user_id == current_user.id, Notification.is_read.is_(False)
        )
    ) or 0
    return UnreadCountResponse(unread_count=count)


@router.post("/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark a specific notification as read (FR-080)."""
    notif = get_user_record(
        db, Notification, current_user.id, notification_id, "NOTIFICATION_NOT_FOUND", "Notification not found."
    )
    notif.is_read = True
    db.commit()
    db.refresh(notif)
    return NotificationResponse.model_validate(notif)


@router.post("/read-all", status_code=status.HTTP_200_OK)
def mark_all_notifications_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark all notifications as read for current user (FR-080)."""
    db.execute(
        update(Notification)
        .where(Notification.user_id == current_user.id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    db.commit()
    return {"message": "All notifications marked as read."}
