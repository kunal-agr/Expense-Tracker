from datetime import date
from typing import Dict, Any, List
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session

from app.models.budget import Budget, BudgetAlert
from app.models.category import Category
from app.models.transaction import Transaction
from app.models.notification import Notification
from app.services.time_utils import (
    get_current_month_str,
    get_previous_month_str,
    get_month_date_range,
)


def calculate_month_expense(db: Session, user_id: int, month_str: str, category_id: int | None = None) -> int:
    """
    Calculate total expense for a user in a given month (YYYY-MM).
    If category_id is provided, includes spending in category and any child subcategories.
    Goal contributions are NOT included (FR-044).
    """
    start_d, end_d = get_month_date_range(month_str)

    stmt = select(func.coalesce(func.sum(Transaction.amount), 0)).where(
        Transaction.user_id == user_id,
        Transaction.type == "expense",
        Transaction.date >= start_d,
        Transaction.date <= end_d,
    )

    if category_id is not None:
        sub_ids = list(
            db.scalars(
                select(Category.id).where(
                    Category.user_id == user_id, Category.parent_id == category_id
                )
            ).all()
        )
        cat_ids = [category_id] + sub_ids
        stmt = stmt.where(
            or_(
                Transaction.category_id.in_(cat_ids),
                Transaction.subcategory_id.in_(cat_ids),
            )
        )

    return int(db.scalar(stmt) or 0)


def calculate_effective_overall_budget(db: Session, user_id: int, target_month: str) -> Dict[str, Any]:
    """
    Calculate effective overall budget for target_month with carry-forward (FR-043).
    Chains month-to-month unused carry-forward from effective_from up to target_month.
    effective(M) = base + max(0, effective(M-1) - spent(M-1))
    """
    overall_budget = db.scalar(
        select(Budget).where(Budget.user_id == user_id, Budget.scope == "overall")
    )
    if not overall_budget:
        return {
            "has_budget": False,
            "base_budget": 0,
            "effective_budget": 0,
            "carry_forward": 0,
            "spent": 0,
            "remaining": 0,
            "percentage": 0.0,
        }

    base = overall_budget.amount
    effective_from = overall_budget.effective_from  # 'YYYY-MM'

    # Build ordered list of months from effective_from to target_month
    # If target_month < effective_from, no carry forward before start
    if target_month < effective_from:
        months_chain = [target_month]
    else:
        months_chain = []
        curr = effective_from
        while curr <= target_month:
            months_chain.append(curr)
            # Advance month
            y, m = map(int, curr.split("-"))
            if m == 12:
                curr = f"{y + 1:04d}-01"
            else:
                curr = f"{y:04d}-{m + 1:02d}"

    effective_map: Dict[str, int] = {}
    carry_forward_map: Dict[str, int] = {}

    for idx, m_str in enumerate(months_chain):
        if idx == 0:
            carry_forward = 0
            effective = base
        else:
            prev_m = months_chain[idx - 1]
            prev_eff = effective_map[prev_m]
            prev_spent = calculate_month_expense(db, user_id, prev_m)
            unused = max(0, prev_eff - prev_spent)
            carry_forward = unused
            effective = base + carry_forward

        effective_map[m_str] = effective
        carry_forward_map[m_str] = carry_forward

    target_effective = effective_map.get(target_month, base)
    target_carry = carry_forward_map.get(target_month, 0)
    target_spent = calculate_month_expense(db, user_id, target_month)
    remaining = target_effective - target_spent
    percentage = round((target_spent / target_effective) * 100, 1) if target_effective > 0 else 0.0

    return {
        "has_budget": True,
        "base_budget": base,
        "effective_budget": target_effective,
        "carry_forward": target_carry,
        "spent": target_spent,
        "remaining": remaining,
        "percentage": percentage,
    }


def check_and_trigger_budget_alerts(db: Session, user_id: int, tx_date: date) -> List[str]:
    """
    Check if current spending crosses 80% or 100% threshold for overall or category budgets (FR-045).
    Fires at most once per budget per month per threshold.
    Returns list of notification messages generated.
    """
    month_str = tx_date.strftime("%Y-%m")
    alerts_triggered = []

    # 1. Check Overall Budget
    overall_status = calculate_effective_overall_budget(db, user_id, month_str)
    if overall_status["has_budget"] and overall_status["effective_budget"] > 0:
        overall_budget = db.scalar(
            select(Budget).where(Budget.user_id == user_id, Budget.scope == "overall")
        )
        eff = overall_status["effective_budget"]
        spent = overall_status["spent"]

        # Check 80% threshold
        if spent >= int(0.80 * eff):
            _trigger_alert_if_not_fired(
                db, user_id, overall_budget.id, month_str, 80,
                f"Budget alert: You have reached 80% of your overall monthly budget (₹{spent}/₹{eff}).",
                alerts_triggered,
            )
        # Check 100% threshold
        if spent >= eff:
            _trigger_alert_if_not_fired(
                db, user_id, overall_budget.id, month_str, 100,
                f"Budget alert: You have reached 100% of your overall monthly budget (₹{spent}/₹{eff}).",
                alerts_triggered,
            )

    # 2. Check Category Budgets
    cat_budgets = db.scalars(
        select(Budget).where(Budget.user_id == user_id, Budget.scope == "category")
    ).all()

    for cb in cat_budgets:
        spent = calculate_month_expense(db, user_id, month_str, cb.category_id)
        limit = cb.amount
        cat = db.scalar(select(Category).where(Category.id == cb.category_id))
        cat_name = cat.name if cat else "Category"

        if spent >= int(0.80 * limit):
            _trigger_alert_if_not_fired(
                db, user_id, cb.id, month_str, 80,
                f"Budget alert: You have reached 80% of your budget for '{cat_name}' (₹{spent}/₹{limit}).",
                alerts_triggered,
            )
        if spent >= limit:
            _trigger_alert_if_not_fired(
                db, user_id, cb.id, month_str, 100,
                f"Budget alert: You have reached 100% of your budget for '{cat_name}' (₹{spent}/₹{limit}).",
                alerts_triggered,
            )

    return alerts_triggered


def _trigger_alert_if_not_fired(
    db: Session,
    user_id: int,
    budget_id: int,
    month: str,
    threshold: int,
    message: str,
    alerts_collector: List[str],
) -> None:
    """Helper to record unique budget alert and send in-app notification (FR-045)."""
    existing = db.scalar(
        select(BudgetAlert.id).where(
            BudgetAlert.budget_id == budget_id,
            BudgetAlert.month == month,
            BudgetAlert.threshold == threshold,
        )
    )
    if not existing:
        alert = BudgetAlert(
            budget_id=budget_id,
            month=month,
            threshold=threshold,
        )
        db.add(alert)
        notif = Notification(
            user_id=user_id,
            type=f"budget_{threshold}",
            payload={"message": message, "budget_id": budget_id, "month": month, "threshold": threshold},
            is_read=False,
        )
        db.add(notif)
        db.flush()
        alerts_collector.append(message)
