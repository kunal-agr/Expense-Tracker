from datetime import datetime, date as py_date, timezone
from sqlalchemy import Integer, BigInteger, String, Boolean, Date, DateTime, ForeignKey, CheckConstraint, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class RecurringRule(Base):
    __tablename__ = "recurring_rules"
    __table_args__ = (
        CheckConstraint("amount >= 1", name="chk_recurring_amount_positive"),
        CheckConstraint("type IN ('income', 'expense')", name="chk_recurring_type"),
        CheckConstraint("day_of_month >= 1 AND day_of_month <= 31", name="chk_recurring_day_of_month"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'income' or 'expense'
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    category_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    payment_method: Mapped[str] = mapped_column(String(20), nullable=False)  # 'UPI', 'Card', 'Cash'
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    frequency: Mapped[str] = mapped_column(String(20), default="monthly", nullable=False)
    day_of_month: Mapped[int] = mapped_column(Integer, nullable=False)  # 1 to 31
    start_date: Mapped[py_date] = mapped_column(Date, nullable=False)
    end_date: Mapped[py_date | None] = mapped_column(Date, nullable=True)
    is_paused: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    user = relationship("User", back_populates="recurring_rules")
    category = relationship("Category")
    runs = relationship("RecurringRun", back_populates="rule", cascade="all, delete-orphan")


class RecurringRun(Base):
    __tablename__ = "recurring_runs"
    __table_args__ = (
        UniqueConstraint("rule_id", "run_date", name="uq_recurring_run_rule_date"),
        CheckConstraint("status IN ('applied', 'skipped')", name="chk_recurring_run_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("recurring_rules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_date: Mapped[py_date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # 'applied' or 'skipped'
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    rule = relationship("RecurringRule", back_populates="runs")
