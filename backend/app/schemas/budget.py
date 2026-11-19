from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class OverallBudgetSetRequest(BaseModel):
    amount: int = Field(ge=1, description="Overall monthly budget in whole rupees")


class CategoryBudgetSetRequest(BaseModel):
    amount: int = Field(ge=1, description="Category monthly budget in whole rupees")


class OverallBudgetResponse(BaseModel):
    id: int
    user_id: int
    amount: int
    effective_from: str
    created_at: datetime

    class Config:
        from_attributes = True


class CategoryBudgetResponse(BaseModel):
    id: int
    user_id: int
    category_id: int
    category_name: str
    amount: int
    created_at: datetime

    class Config:
        from_attributes = True


class CategoryBudgetStatusItem(BaseModel):
    category_id: int
    category_name: str
    budget_amount: int
    spent: int
    remaining: int
    percentage: float


class OverallBudgetStatus(BaseModel):
    has_budget: bool
    base_budget: int
    effective_budget: int
    carry_forward: int
    spent: int
    remaining: int
    percentage: float


class BudgetStatusResponse(BaseModel):
    month: str
    overall: OverallBudgetStatus
    categories: List[CategoryBudgetStatusItem]
    sum_category_budgets: int
