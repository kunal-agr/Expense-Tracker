from datetime import datetime, date as py_date, timezone
from sqlalchemy import Integer, BigInteger, String, Boolean, Date, DateTime, ForeignKey, CheckConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("amount >= 1", name="chk_transaction_amount_positive"),
        CheckConstraint("type IN ('income', 'expense')", name="chk_transaction_type"),
        CheckConstraint("source IN ('manual', 'recurring', 'split')", name="chk_transaction_source"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    wallet_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("wallets.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'income' or 'expense'
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    date: Mapped[py_date] = mapped_column(Date, nullable=False, index=True)
    category_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    subcategory_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("categories.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    payment_method: Mapped[str] = mapped_column(String(20), nullable=False)  # 'UPI', 'Card', 'Cash'
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="manual", nullable=False)  # 'manual', 'recurring', 'split'
    split_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("splits.id", ondelete="SET NULL"), nullable=True, index=True
    )
    read_only: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    user = relationship("User", back_populates="transactions")
    wallet = relationship("Wallet", back_populates="transactions")
    category = relationship("Category", foreign_keys=[category_id], back_populates="transactions")
    subcategory = relationship("Category", foreign_keys=[subcategory_id], back_populates="subcategory_transactions")
    split = relationship("Split", back_populates="transactions")
