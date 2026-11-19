from datetime import datetime, timezone
from sqlalchemy import Integer, String, DateTime, ForeignKey, UniqueConstraint, CheckConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    creator_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    creator = relationship("User", foreign_keys=[creator_id])
    members = relationship("GroupMember", back_populates="group", cascade="all, delete-orphan")
    splits = relationship("Split", back_populates="group")


class GroupMember(Base):
    __tablename__ = "group_members"
    __table_args__ = (
        UniqueConstraint("group_id", "user_id", name="uq_group_member"),
        CheckConstraint("status IN ('invited', 'active')", name="chk_group_member_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="invited", nullable=False)  # 'invited', 'active'

    group = relationship("Group", back_populates="members")
    user = relationship("User")
