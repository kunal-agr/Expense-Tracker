from datetime import date
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, and_, desc, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.wallet import Wallet
from app.models.category import Category
from app.models.transaction import Transaction
from app.models.goal import Goal
from app.models.budget import Budget
from app.schemas.dashboard import (
    DashboardResponse,
    MonthSummary,
    CategorySpendingItem,
    MonthTrendItem,
)
from app.schemas.transaction import TransactionResponse
from app.schemas.goal import GoalResponse
from app.schemas.budget import (
    BudgetStatusResponse,
    OverallBudgetStatus,
    CategoryBudgetStatusItem,
)
from app.auth.dependencies import get_current_user
from app.services.time_utils import (
    get_current_month_str,
    get_month_date_range,
    get_previous_month_str,
)
from app.services.budget_service import (
    calculate_effective_overall_budget,
    calculate_month_expense,
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("", response_model=DashboardResponse)
def get_dashboard_data(
    month: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}$", description="Month formatted YYYY-MM"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get full analytics dashboard data for the selected month (FR-090).
    Current balance, income vs expense, category donut data, budget status,
    goals progress, recent transactions, and 6-month historical trend.
    """
    selected_month = month or get_current_month_str()
    start_d, end_d = get_month_date_range(selected_month)

    # 1. Current wallet balance
    wallet = db.scalar(select(Wallet).where(Wallet.user_id == current_user.id))
    current_balance = wallet.current_balance if wallet else 0

    # 2. Month income and expense
    inc_sum = db.scalar(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.user_id == current_user.id,
            Transaction.type == "income",
            Transaction.date >= start_d,
            Transaction.date <= end_d,
        )
    ) or 0

    exp_sum = db.scalar(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.user_id == current_user.id,
            Transaction.type == "expense",
            Transaction.date >= start_d,
            Transaction.date <= end_d,
        )
    ) or 0

    this_month = MonthSummary(
        income=inc_sum,
        expense=exp_sum,
        net=inc_sum - exp_sum,
    )

    # 3. Category spending breakdown (aggregating subcategories into parent categories)
    # Fetch all expense transactions for the month
    month_expenses = db.scalars(
        select(Transaction).where(
            Transaction.user_id == current_user.id,
            Transaction.type == "expense",
            Transaction.date >= start_d,
            Transaction.date <= end_d,
        )
    ).all()

    # Pre-fetch user categories
    user_cats = db.scalars(
        select(Category).where(Category.user_id == current_user.id)
    ).all()
    cat_lookup = {c.id: c for c in user_cats}

    cat_totals = {}
    for tx in month_expenses:
        cat = cat_lookup.get(tx.category_id)
        if not cat:
            continue
        # If this is a subcategory, attribute to parent
        top_cat = cat_lookup.get(cat.parent_id) if cat.parent_id else cat
        cat_totals[top_cat.id] = cat_totals.get(top_cat.id, 0) + tx.amount

    category_spending = []
    for cat_id, amt in sorted(cat_totals.items(), key=lambda x: x[1], reverse=True):
        cat_obj = cat_lookup.get(cat_id)
        c_name = cat_obj.name if cat_obj else "Other"
        pct = round((amt / exp_sum) * 100, 1) if exp_sum > 0 else 0.0
        category_spending.append(
            CategorySpendingItem(
                category_id=cat_id,
                category_name=c_name,
                amount=amt,
                percentage=pct,
            )
        )

    # 4. Budget progress
    overall_data = calculate_effective_overall_budget(db, current_user.id, selected_month)
    cat_budgets = db.execute(
        select(Budget, Category.name.label("category_name"))
        .join(Category, Category.id == Budget.category_id)
        .where(Budget.user_id == current_user.id, Budget.scope == "category")
        .order_by(Category.name.asc())
    ).all()

    cat_items = []
    cat_sum = 0
    for cb, c_name in cat_budgets:
        cat_sum += cb.amount
        c_spent = calculate_month_expense(db, current_user.id, selected_month, cb.category_id)
        rem = cb.amount - c_spent
        pct = round((c_spent / cb.amount) * 100, 1) if cb.amount > 0 else 0.0
        cat_items.append(
            CategoryBudgetStatusItem(
                category_id=cb.category_id,
                category_name=c_name,
                budget_amount=cb.amount,
                spent=c_spent,
                remaining=rem,
                percentage=pct,
            )
        )

    budget_progress = BudgetStatusResponse(
        month=selected_month,
        overall=OverallBudgetStatus(**overall_data),
        categories=cat_items,
        sum_category_budgets=cat_sum,
    )

    # 5. Recent transactions (last 6)
    recent_txs = db.execute(
        select(Transaction, Category.name.label("category_name"))
        .join(Category, Category.id == Transaction.category_id)
        .where(Transaction.user_id == current_user.id)
        .order_by(desc(Transaction.date), desc(Transaction.id))
        .limit(6)
    ).all()

    sub_ids = [r[0].subcategory_id for r in recent_txs if r[0].subcategory_id]
    sub_map = {}
    if sub_ids:
        subs = db.scalars(select(Category).where(Category.id.in_(sub_ids))).all()
        sub_map = {s.id: s.name for s in subs}

    recent_list = []
    for tx_obj, c_name in recent_txs:
        recent_list.append(
            TransactionResponse(
                id=tx_obj.id,
                user_id=tx_obj.user_id,
                wallet_id=tx_obj.wallet_id,
                type=tx_obj.type,
                amount=tx_obj.amount,
                date=tx_obj.date,
                category_id=tx_obj.category_id,
                category_name=c_name,
                subcategory_id=tx_obj.subcategory_id,
                subcategory_name=sub_map.get(tx_obj.subcategory_id),
                payment_method=tx_obj.payment_method,
                note=tx_obj.note,
                source=tx_obj.source,
                read_only=tx_obj.read_only,
                created_at=tx_obj.created_at,
            )
        )

    # 6. Savings goals progress
    goals = db.scalars(
        select(Goal).where(Goal.user_id == current_user.id).order_by(Goal.created_at.desc())
    ).all()
    goals_progress = []
    for g in goals:
        pct = round((g.saved_amount / g.target_amount) * 100, 1) if g.target_amount > 0 else 0.0
        goals_progress.append(
            GoalResponse(
                id=g.id,
                user_id=g.user_id,
                name=g.name,
                target_amount=g.target_amount,
                saved_amount=g.saved_amount,
                deadline=g.deadline,
                status=g.status,
                created_at=g.created_at,
                percentage=min(pct, 100.0),
            )
        )

    # 7. Income vs expense trend (last 6 months in chronological order)
    # Build list of 6 months ending in selected_month
    curr_m = selected_month
    six_months = []
    for _ in range(6):
        six_months.append(curr_m)
        curr_m = get_previous_month_str(curr_m)
    six_months.reverse()

    trend_list = []
    for m_str in six_months:
        m_start, m_end = get_month_date_range(m_str)
        m_inc = db.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.user_id == current_user.id,
                Transaction.type == "income",
                Transaction.date >= m_start,
                Transaction.date <= m_end,
            )
        ) or 0
        m_exp = db.scalar(
            select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                Transaction.user_id == current_user.id,
                Transaction.type == "expense",
                Transaction.date >= m_start,
                Transaction.date <= m_end,
            )
        ) or 0
        trend_list.append(
            MonthTrendItem(
                month=m_str,
                income=m_inc,
                expense=m_exp,
                net=m_inc - m_exp,
            )
        )

    return DashboardResponse(
        current_balance=current_balance,
        selected_month=selected_month,
        this_month=this_month,
        category_spending=category_spending,
        budget_progress=budget_progress,
        recent_transactions=recent_list,
        goals_progress=goals_progress,
        trend_6_months=trend_list,
    )
