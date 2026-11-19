from datetime import datetime, timezone
from sqlalchemy import Integer, BigInteger, String, DateTime, ForeignKey, CheckConstraint, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class Budget(Base):
    __tablename__ = "budgets"
    __table_args__ = (
        CheckConstraint("amount >= 1", name="chk_budget_amount_positive"),
        CheckConstraint("scope IN ('overall', 'category')", name="chk_budget_scope"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scope: Mapped[str] = mapped_column(String(20), nullable=False)  # 'overall' or 'category'
    category_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("categories.id", ondelete="CASCADE"), nullable=True, index=True
    )
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    effective_from: Mapped[str] = mapped_column(String(7), nullable=False)  # 'YYYY-MM'
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    user = relationship("User", back_populates="budgets")
    category = relationship("Category", back_populates="budget")
    alerts = relationship("BudgetAlert", back_populates="budget", cascade="all, delete-orphan")


class BudgetAlert(Base):
    __tablename__ = "budget_alerts"
    __table_args__ = (
        UniqueConstraint("budget_id", "month", "threshold", name="uq_budget_alert_month_threshold"),
        CheckConstraint("threshold IN (80, 100)", name="chk_budget_alert_threshold"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    budget_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("budgets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    month: Mapped[str] = mapped_column(String(7), nullable=False)  # 'YYYY-MM'
    threshold: Mapped[int] = mapped_column(Integer, nullable=False)  # 80 or 100
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    budget = relationship("Budget", back_populates="alerts")
