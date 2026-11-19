from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel
from app.schemas.transaction import TransactionResponse
from app.schemas.budget import BudgetStatusResponse
from app.schemas.goal import GoalResponse


class MonthSummary(BaseModel):
    income: int
    expense: int
    net: int


class CategorySpendingItem(BaseModel):
    category_id: int
    category_name: str
    amount: int
    percentage: float


class MonthTrendItem(BaseModel):
    month: str  # YYYY-MM
    income: int
    expense: int
    net: int


class DashboardResponse(BaseModel):
    current_balance: int
    selected_month: str
    this_month: MonthSummary
    category_spending: List[CategorySpendingItem]
    budget_progress: BudgetStatusResponse
    recent_transactions: List[TransactionResponse]
    goals_progress: List[GoalResponse]
    trend_6_months: List[MonthTrendItem]
