from datetime import datetime, timezone
from sqlalchemy import Integer, BigInteger, String, DateTime, ForeignKey, CheckConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class Split(Base):
    __tablename__ = "splits"
    __table_args__ = (
        CheckConstraint("total_amount >= 1", name="chk_split_total_amount_positive"),
        CheckConstraint("split_type IN ('exact', 'percentage', 'shares')", name="chk_split_type"),
        CheckConstraint("status IN ('pending', 'locked', 'cancelled')", name="chk_split_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    payer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    group_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("groups.id", ondelete="SET NULL"), nullable=True, index=True
    )
    total_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    split_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'exact', 'percentage', 'shares'
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)  # 'pending', 'locked', 'cancelled'
    remainder_bearer_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    payer = relationship("User", foreign_keys=[payer_id])
    remainder_bearer = relationship("User", foreign_keys=[remainder_bearer_id])
    group = relationship("Group", back_populates="splits")
    participants = relationship("SplitParticipant", back_populates="split", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="split")


class SplitParticipant(Base):
    __tablename__ = "split_participants"
    __table_args__ = (
        CheckConstraint("share_amount >= 0", name="chk_split_participant_share_amount"),
        CheckConstraint("status IN ('pending', 'accepted', 'rejected', 'expired')", name="chk_split_participant_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    split_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("splits.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    share_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)  # 'pending', 'accepted', 'rejected', 'expired'
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    split = relationship("Split", back_populates="participants")
    user = relationship("User")
