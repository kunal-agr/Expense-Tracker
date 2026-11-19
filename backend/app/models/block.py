from datetime import datetime, timezone
from sqlalchemy import Integer, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class Block(Base):
    __tablename__ = "blocks"
    __table_args__ = (
        UniqueConstraint("blocker_id", "blocked_id", name="uq_blocker_blocked"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    blocker_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    blocked_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    blocker = relationship("User", foreign_keys=[blocker_id], back_populates="blocks_initiated")
    blocked = relationship("User", foreign_keys=[blocked_id], back_populates="blocks_received")
