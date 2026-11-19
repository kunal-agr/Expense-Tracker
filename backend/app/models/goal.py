from datetime import datetime, date as py_date, timezone
from sqlalchemy import Integer, BigInteger, String, Date, DateTime, ForeignKey, CheckConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class Goal(Base):
    __tablename__ = "goals"
    __table_args__ = (
        CheckConstraint("target_amount >= 1", name="chk_goal_target_amount_positive"),
        CheckConstraint("saved_amount >= 0", name="chk_goal_saved_amount_non_negative"),
        CheckConstraint("status IN ('in_progress', 'completed')", name="chk_goal_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    target_amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    saved_amount: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    deadline: Mapped[py_date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="in_progress", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    user = relationship("User", back_populates="goals")
    entries = relationship("GoalEntry", back_populates="goal", cascade="all, delete-orphan")


class GoalEntry(Base):
    __tablename__ = "goal_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    goal_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("goals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)  # positive for contribution, negative for withdrawal
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    goal = relationship("Goal", back_populates="entries")
