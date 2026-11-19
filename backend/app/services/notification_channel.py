from abc import ABC, abstractmethod
from typing import Dict, Any
from sqlalchemy.orm import Session
from app.models.notification import Notification


class BaseNotificationChannel(ABC):
    @abstractmethod
    def send(self, db: Session, user_id: int, notification_type: str, payload: Dict[str, Any]) -> None:
        """Send notification through channel."""
        pass


class InAppNotificationChannel(BaseNotificationChannel):
    """In-app persistent notification channel for v1 (FR-084)."""

    def send(self, db: Session, user_id: int, notification_type: str, payload: Dict[str, Any]) -> Notification:
        notif = Notification(
            user_id=user_id,
            type=notification_type,
            payload=payload,
            is_read=False,
        )
        db.add(notif)
        db.flush()
        return notif


# Global channel manager with future v2 extensibility (e.g. EmailChannel)
class NotificationService:
    def __init__(self):
        self.channels: list[BaseNotificationChannel] = [InAppNotificationChannel()]

    def notify(self, db: Session, user_id: int, notification_type: str, payload: Dict[str, Any]) -> None:
        for channel in self.channels:
            channel.send(db, user_id, notification_type, payload)


notification_service = NotificationService()
