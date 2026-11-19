from datetime import datetime, timezone
from sqlalchemy import Integer, String, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("categories.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'income' or 'expense'
    is_protected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    user = relationship("User", back_populates="categories")
    parent = relationship("Category", remote_side=[id], back_populates="subcategories")
    subcategories = relationship(
        "Category", back_populates="parent", cascade="all, delete-orphan"
    )
    transactions = relationship(
        "Transaction", foreign_keys="Transaction.category_id", back_populates="category"
    )
    subcategory_transactions = relationship(
        "Transaction", foreign_keys="Transaction.subcategory_id", back_populates="subcategory"
    )
    budget = relationship("Budget", back_populates="category", uselist=False, cascade="all, delete-orphan")
