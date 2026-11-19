import math
from datetime import date as py_date
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select, func, or_, desc, asc
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.wallet import Wallet
from app.models.category import Category
from app.models.transaction import Transaction
from app.schemas.transaction import (
    TransactionCreate,
    TransactionUpdate,
    TransactionResponse,
    TransactionListResponse,
)
from app.auth.dependencies import get_current_user, get_user_record
from app.services.budget_service import check_and_trigger_budget_alerts
from app.errors import AppException

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.post("", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(
    payload: TransactionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new income or expense transaction (FR-023).
    Validates category, date, payment method, and wallet balance.
    Expense operations run with row-level wallet locks and enforce balance invariant (FR-022, FR-025).
    """
    # Verify category ownership and type match
    category = get_user_record(
        db, Category, current_user.id, payload.category_id, "CATEGORY_NOT_FOUND", "Category not found."
    )
    if category.type != payload.type:
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="CATEGORY_TYPE_MISMATCH",
            message=f"Category '{category.name}' is of type '{category.type}', cannot be used for a '{payload.type}' transaction.",
        )

    # Verify subcategory if provided
    subcategory = None
    if payload.subcategory_id is not None:
        subcategory = get_user_record(
            db, Category, current_user.id, payload.subcategory_id, "SUBCATEGORY_NOT_FOUND", "Subcategory not found."
        )
        if subcategory.parent_id != category.id:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="INVALID_SUBCATEGORY",
                message=f"Subcategory '{subcategory.name}' does not belong to category '{category.name}'.",
            )

    # Lock wallet row for balance verification and atomic update (FR-022, NFR-010)
    wallet = db.scalar(
        select(Wallet).where(Wallet.user_id == current_user.id).with_for_update()
    )
    if not wallet:
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="WALLET_NOT_INITIALIZED",
            message="Please complete opening balance setup before recording transactions.",
        )

    if payload.type == "expense":
        if wallet.current_balance < payload.amount:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="INSUFFICIENT_FUNDS",
                message=f"Expense of ₹{payload.amount} exceeds current wallet balance of ₹{wallet.current_balance}.",
            )
        wallet.current_balance -= payload.amount
    else:  # income
        wallet.current_balance += payload.amount

    tx = Transaction(
        user_id=current_user.id,
        wallet_id=wallet.id,
        type=payload.type,
        amount=payload.amount,
        date=payload.date,
        category_id=category.id,
        subcategory_id=subcategory.id if subcategory else None,
        payment_method=payload.payment_method,
        note=payload.note,
        source="manual",
        read_only=False,
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)

    # Check budget alerts if expense (FR-045, FR-046)
    if tx.type == "expense":
        check_and_trigger_budget_alerts(db, current_user.id, tx.date)
        db.commit()

    return TransactionResponse(
        id=tx.id,
        user_id=tx.user_id,
        wallet_id=tx.wallet_id,
        type=tx.type,
        amount=tx.amount,
        date=tx.date,
        category_id=tx.category_id,
        category_name=category.name,
        subcategory_id=tx.subcategory_id,
        subcategory_name=subcategory.name if subcategory else None,
        payment_method=tx.payment_method,
        note=tx.note,
        source=tx.source,
        read_only=tx.read_only,
        created_at=tx.created_at,
    )


@router.get("", response_model=TransactionListResponse)
def list_transactions(
    search: Optional[str] = Query(None, description="Search note text"),
    from_date: Optional[py_date] = Query(None, description="Start date (inclusive)"),
    to_date: Optional[py_date] = Query(None, description="End date (inclusive)"),
    category_id: Optional[int] = Query(None, description="Category filter"),
    type: Optional[str] = Query(None, pattern="^(income|expense)$"),
    payment_method: Optional[str] = Query(None, pattern="^(UPI|Card|Cash)$"),
    sort_by: str = Query("date", pattern="^(date|amount)$"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List transactions with search, multi-field filtering, sorting, and pagination (FR-028)."""
    stmt = (
        select(
            Transaction,
            Category.name.label("category_name"),
        )
        .join(Category, Category.id == Transaction.category_id)
        .where(Transaction.user_id == current_user.id)
    )

    if search:
        search_pattern = f"%{search.strip()}%"
        stmt = stmt.where(Transaction.note.ilike(search_pattern))

    if from_date:
        stmt = stmt.where(Transaction.date >= from_date)
    if to_date:
        stmt = stmt.where(Transaction.date <= to_date)
    if category_id:
        stmt = stmt.where(
            or_(
                Transaction.category_id == category_id,
                Transaction.subcategory_id == category_id,
            )
        )
    if type:
        stmt = stmt.where(Transaction.type == type)
    if payment_method:
        stmt = stmt.where(Transaction.payment_method == payment_method)

    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.scalar(count_stmt) or 0

    # Sorting
    sort_col = Transaction.date if sort_by == "date" else Transaction.amount
    order_clause = desc(sort_col) if sort_dir == "desc" else asc(sort_col)
    stmt = stmt.order_by(order_clause, desc(Transaction.id))

    # Pagination
    offset = (page - 1) * limit
    stmt = stmt.offset(offset).limit(limit)

    results = db.execute(stmt).all()

    # Pre-fetch subcategories for returned rows
    sub_ids = [row[0].subcategory_id for row in results if row[0].subcategory_id is not None]
    sub_map = {}
    if sub_ids:
        subs = db.scalars(select(Category).where(Category.id.in_(sub_ids))).all()
        sub_map = {s.id: s.name for s in subs}

    items = []
    for tx, cat_name in results:
        items.append(
            TransactionResponse(
                id=tx.id,
                user_id=tx.user_id,
                wallet_id=tx.wallet_id,
                type=tx.type,
                amount=tx.amount,
                date=tx.date,
                category_id=tx.category_id,
                category_name=cat_name,
                subcategory_id=tx.subcategory_id,
                subcategory_name=sub_map.get(tx.subcategory_id),
                payment_method=tx.payment_method,
                note=tx.note,
                source=tx.source,
                read_only=tx.read_only,
                created_at=tx.created_at,
            )
        )

    pages = math.ceil(total / limit) if total > 0 else 1
    return TransactionListResponse(
        items=items,
        total=total,
        page=page,
        limit=limit,
        pages=pages,
    )


@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction(
    transaction_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve details of a single transaction scoped to authenticated user."""
    tx = get_user_record(
        db, Transaction, current_user.id, transaction_id, "TRANSACTION_NOT_FOUND", "Transaction not found."
    )
    category = db.scalar(select(Category).where(Category.id == tx.category_id))
    subcategory = (
        db.scalar(select(Category).where(Category.id == tx.subcategory_id))
        if tx.subcategory_id
        else None
    )

    return TransactionResponse(
        id=tx.id,
        user_id=tx.user_id,
        wallet_id=tx.wallet_id,
        type=tx.type,
        amount=tx.amount,
        date=tx.date,
        category_id=tx.category_id,
        category_name=category.name if category else None,
        subcategory_id=tx.subcategory_id,
        subcategory_name=subcategory.name if subcategory else None,
        payment_method=tx.payment_method,
        note=tx.note,
        source=tx.source,
        read_only=tx.read_only,
        created_at=tx.created_at,
    )


@router.patch("/{transaction_id}", response_model=TransactionResponse)
def update_transaction(
    transaction_id: int,
    payload: TransactionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Edit transaction (FR-023). Read-only transactions cannot be modified (FR-027).
    Modifying amount checks current wallet balance invariant (FR-026).
    """
    tx = get_user_record(
        db, Transaction, current_user.id, transaction_id, "TRANSACTION_NOT_FOUND", "Transaction not found."
    )

    if tx.read_only:
        raise AppException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="READ_ONLY_TRANSACTION",
            message="Transactions generated by split bills are read-only and cannot be edited.",
        )

    wallet = db.scalar(
        select(Wallet).where(Wallet.user_id == current_user.id).with_for_update()
    )

    # Check category change if provided
    if payload.category_id is not None:
        cat = get_user_record(
            db, Category, current_user.id, payload.category_id, "CATEGORY_NOT_FOUND", "Category not found."
        )
        if cat.type != tx.type:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="CATEGORY_TYPE_MISMATCH",
                message=f"Category '{cat.name}' type '{cat.type}' does not match transaction type '{tx.type}'.",
            )
        tx.category_id = cat.id

    if payload.subcategory_id is not None:
        sub = get_user_record(
            db, Category, current_user.id, payload.subcategory_id, "SUBCATEGORY_NOT_FOUND", "Subcategory not found."
        )
        if sub.parent_id != tx.category_id:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="INVALID_SUBCATEGORY",
                message="Subcategory does not belong to the selected category.",
            )
        tx.subcategory_id = sub.id

    # Handle amount change with balance verification (FR-026)
    if payload.amount is not None and payload.amount != tx.amount:
        new_amount = payload.amount
        if tx.type == "expense":
            # Difference: if new_amount > tx.amount, we need more money from wallet
            delta = new_amount - tx.amount
            if wallet.current_balance < delta:
                raise AppException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="BALANCE_WOULD_BE_NEGATIVE",
                    message=f"Increasing expense to ₹{new_amount} exceeds available balance.",
                )
            wallet.current_balance -= delta
        else:  # income
            # If income decreased, wallet balance decreases
            delta = tx.amount - new_amount
            if wallet.current_balance < delta:
                raise AppException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="BALANCE_WOULD_BE_NEGATIVE",
                    message=f"Decreasing income to ₹{new_amount} would cause current balance to drop below zero.",
                )
            wallet.current_balance -= delta
        tx.amount = new_amount

    if payload.date is not None:
        tx.date = payload.date
    if payload.payment_method is not None:
        tx.payment_method = payload.payment_method
    if payload.note is not None:
        tx.note = payload.note

    db.commit()
    db.refresh(tx)

    if tx.type == "expense":
        check_and_trigger_budget_alerts(db, current_user.id, tx.date)
        db.commit()

    category = db.scalar(select(Category).where(Category.id == tx.category_id))
    subcategory = (
        db.scalar(select(Category).where(Category.id == tx.subcategory_id))
        if tx.subcategory_id
        else None
    )

    return TransactionResponse(
        id=tx.id,
        user_id=tx.user_id,
        wallet_id=tx.wallet_id,
        type=tx.type,
        amount=tx.amount,
        date=tx.date,
        category_id=tx.category_id,
        category_name=category.name if category else None,
        subcategory_id=tx.subcategory_id,
        subcategory_name=subcategory.name if subcategory else None,
        payment_method=tx.payment_method,
        note=tx.note,
        source=tx.source,
        read_only=tx.read_only,
        created_at=tx.created_at,
    )


@router.delete("/{transaction_id}", status_code=status.HTTP_200_OK)
def delete_transaction(
    transaction_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete transaction (FR-023). Read-only transactions cannot be deleted (FR-027).
    Deleting an income checks current balance invariant (FR-026).
    """
    tx = get_user_record(
        db, Transaction, current_user.id, transaction_id, "TRANSACTION_NOT_FOUND", "Transaction not found."
    )

    if tx.read_only:
        raise AppException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="READ_ONLY_TRANSACTION",
            message="Transactions generated by split bills are read-only and cannot be deleted.",
        )

    wallet = db.scalar(
        select(Wallet).where(Wallet.user_id == current_user.id).with_for_update()
    )

    if tx.type == "income":
        # Reversing income reduces wallet balance
        if wallet.current_balance < tx.amount:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="BALANCE_WOULD_BE_NEGATIVE",
                message=f"Deleting income of ₹{tx.amount} would cause current balance to drop below zero (current: ₹{wallet.current_balance}).",
            )
        wallet.current_balance -= tx.amount
    else:  # expense
        # Reversing expense restores wallet balance
        wallet.current_balance += tx.amount

    db.delete(tx)
    db.commit()

    return {"message": "Transaction deleted successfully."}
