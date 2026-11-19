from datetime import datetime, timezone
from sqlalchemy import Integer, BigInteger, DateTime, ForeignKey, CheckConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class Wallet(Base):
    __tablename__ = "wallets"
    __table_args__ = (
        CheckConstraint("current_balance >= 0", name="chk_wallet_current_balance_non_negative"),
        CheckConstraint("opening_balance >= 100", name="chk_wallet_opening_balance_min_100"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    opening_balance: Mapped[int] = mapped_column(BigInteger, nullable=False)
    current_balance: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    user = relationship("User", back_populates="wallet")
    transactions = relationship("Transaction", back_populates="wallet")
