from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.budget import Budget
from app.models.category import Category
from app.schemas.budget import (
    OverallBudgetSetRequest,
    CategoryBudgetSetRequest,
    OverallBudgetResponse,
    CategoryBudgetResponse,
    BudgetStatusResponse,
    OverallBudgetStatus,
    CategoryBudgetStatusItem,
)
from app.auth.dependencies import get_current_user, get_user_record
from app.services.time_utils import get_current_month_str
from app.services.budget_service import (
    calculate_effective_overall_budget,
    calculate_month_expense,
)
from app.errors import AppException

router = APIRouter(prefix="/budgets", tags=["Budgets"])


@router.get("/overall", response_model=OverallBudgetResponse)
def get_overall_budget(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve overall monthly base budget (FR-040)."""
    budget = db.scalar(
        select(Budget).where(Budget.user_id == current_user.id, Budget.scope == "overall")
    )
    if not budget:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="BUDGET_NOT_FOUND",
            message="Overall monthly budget has not been set.",
        )
    return budget


@router.put("/overall", response_model=OverallBudgetResponse)
def set_overall_budget(
    payload: OverallBudgetSetRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Set or update overall base budget (FR-040, FR-042).
    Lowering overall budget below the sum of existing category budgets is blocked.
    """
    # Calculate sum of existing category budgets
    cat_budget_sum = db.scalar(
        select(func.coalesce(func.sum(Budget.amount), 0)).where(
            Budget.user_id == current_user.id, Budget.scope == "category"
        )
    ) or 0

    if payload.amount < cat_budget_sum:
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="BUDGET_BELOW_CATEGORIES",
            message=f"Cannot set overall budget to ₹{payload.amount}: sum of category budgets is ₹{cat_budget_sum}.",
        )

    current_month = get_current_month_str()
    budget = db.scalar(
        select(Budget).where(Budget.user_id == current_user.id, Budget.scope == "overall")
    )
    if not budget:
        budget = Budget(
            user_id=current_user.id,
            scope="overall",
            category_id=None,
            amount=payload.amount,
            effective_from=current_month,
        )
        db.add(budget)
    else:
        budget.amount = payload.amount
        budget.effective_from = current_month

    db.commit()
    db.refresh(budget)
    return budget


@router.get("/categories", response_model=List[CategoryBudgetResponse])
def get_category_budgets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all category budgets for authenticated user (FR-041)."""
    stmt = (
        select(Budget, Category.name.label("category_name"))
        .join(Category, Category.id == Budget.category_id)
        .where(Budget.user_id == current_user.id, Budget.scope == "category")
        .order_by(Category.name.asc())
    )
    results = db.execute(stmt).all()
    return [
        CategoryBudgetResponse(
            id=b.id,
            user_id=b.user_id,
            category_id=b.category_id,
            category_name=cat_name,
            amount=b.amount,
            created_at=b.created_at,
        )
        for b, cat_name in results
    ]


@router.put("/categories/{category_id}", response_model=CategoryBudgetResponse)
def set_category_budget(
    category_id: int,
    payload: CategoryBudgetSetRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Set or update a category budget (FR-041, FR-042).
    Overall budget must be set first. Sum of category budgets cannot exceed overall base budget.
    """
    overall = db.scalar(
        select(Budget).where(Budget.user_id == current_user.id, Budget.scope == "overall")
    )
    if not overall:
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="OVERALL_BUDGET_REQUIRED",
            message="Overall monthly budget must be configured before setting category budgets.",
        )

    category = get_user_record(
        db, Category, current_user.id, category_id, "CATEGORY_NOT_FOUND", "Category not found."
    )
    if category.type != "expense":
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_CATEGORY_TYPE",
            message="Budgets can only be set on expense categories.",
        )

    # Check sum of other category budgets + this new amount
    other_cat_sum = db.scalar(
        select(func.coalesce(func.sum(Budget.amount), 0)).where(
            Budget.user_id == current_user.id,
            Budget.scope == "category",
            Budget.category_id != category_id,
        )
    ) or 0

    if other_cat_sum + payload.amount > overall.amount:
        raise AppException(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="BUDGET_EXCEEDS_OVERALL",
            message=f"Category budgets total (₹{other_cat_sum + payload.amount}) cannot exceed overall budget of ₹{overall.amount}.",
        )

    current_month = get_current_month_str()
    cat_budget = db.scalar(
        select(Budget).where(
            Budget.user_id == current_user.id,
            Budget.scope == "category",
            Budget.category_id == category_id,
        )
    )
    if not cat_budget:
        cat_budget = Budget(
            user_id=current_user.id,
            scope="category",
            category_id=category_id,
            amount=payload.amount,
            effective_from=current_month,
        )
        db.add(cat_budget)
    else:
        cat_budget.amount = payload.amount

    db.commit()
    db.refresh(cat_budget)

    return CategoryBudgetResponse(
        id=cat_budget.id,
        user_id=cat_budget.user_id,
        category_id=cat_budget.category_id,
        category_name=category.name,
        amount=cat_budget.amount,
        created_at=cat_budget.created_at,
    )


@router.delete("/categories/{category_id}", status_code=status.HTTP_200_OK)
def delete_category_budget(
    category_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a category budget (FR-041)."""
    cat_budget = db.scalar(
        select(Budget).where(
            Budget.user_id == current_user.id,
            Budget.scope == "category",
            Budget.category_id == category_id,
        )
    )
    if not cat_budget:
        raise AppException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="BUDGET_NOT_FOUND",
            message="Category budget not found.",
        )
    db.delete(cat_budget)
    db.commit()
    return {"message": "Category budget removed successfully."}


@router.get("/status", response_model=BudgetStatusResponse)
def get_budget_status(
    month: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}$", description="Month formatted YYYY-MM"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get comprehensive budget progress and status for a given month (FR-040 - FR-044).
    Includes overall budget with chained carry-forward and individual category budgets.
    """
    target_month = month or get_current_month_str()

    overall_data = calculate_effective_overall_budget(db, current_user.id, target_month)

    # Categories status
    cat_budgets = db.execute(
        select(Budget, Category.name.label("category_name"))
        .join(Category, Category.id == Budget.category_id)
        .where(Budget.user_id == current_user.id, Budget.scope == "category")
        .order_by(Category.name.asc())
    ).all()

    cat_items = []
    cat_sum = 0
    for cb, cat_name in cat_budgets:
        cat_sum += cb.amount
        spent = calculate_month_expense(db, current_user.id, target_month, cb.category_id)
        rem = cb.amount - spent
        pct = round((spent / cb.amount) * 100, 1) if cb.amount > 0 else 0.0
        cat_items.append(
            CategoryBudgetStatusItem(
                category_id=cb.category_id,
                category_name=cat_name,
                budget_amount=cb.amount,
                spent=spent,
                remaining=rem,
                percentage=pct,
            )
        )

    return BudgetStatusResponse(
        month=target_month,
        overall=OverallBudgetStatus(**overall_data),
        categories=cat_items,
        sum_category_budgets=cat_sum,
    )
