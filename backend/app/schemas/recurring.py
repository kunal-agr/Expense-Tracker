from datetime import date as py_date, datetime
from typing import Optional
from pydantic import BaseModel, Field


class RecurringRuleCreate(BaseModel):
    type: str = Field(pattern="^(income|expense)$")
    amount: int = Field(ge=1, description="Amount in whole rupees")
    category_id: int
    payment_method: str = Field(pattern="^(UPI|Card|Cash)$")
    note: Optional[str] = Field(default=None, max_length=500)
    day_of_month: int = Field(ge=1, le=31, description="Day of month (1-31)")
    start_date: py_date
    end_date: Optional[py_date] = None


class RecurringRuleUpdate(BaseModel):
    amount: Optional[int] = Field(default=None, ge=1)
    category_id: Optional[int] = None
    payment_method: Optional[str] = Field(default=None, pattern="^(UPI|Card|Cash)$")
    note: Optional[str] = Field(default=None, max_length=500)
    day_of_month: Optional[int] = Field(default=None, ge=1, le=31)
    end_date: Optional[py_date] = None


class RecurringRuleResponse(BaseModel):
    id: int
    user_id: int
    type: str
    amount: int
    category_id: int
    category_name: Optional[str] = None
    payment_method: str
    note: Optional[str] = None
    frequency: str
    day_of_month: int
    start_date: py_date
    end_date: Optional[py_date] = None
    is_paused: bool
    created_at: datetime

    class Config:
        from_attributes = True
