from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class GoalCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    target_amount: int = Field(ge=1, description="Target amount in whole rupees")
    deadline: Optional[date] = None


class GoalUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    target_amount: Optional[int] = Field(default=None, ge=1)
    deadline: Optional[date] = None


class GoalFundAction(BaseModel):
    amount: int = Field(ge=1, description="Amount in whole rupees")


class GoalEntryResponse(BaseModel):
    id: int
    goal_id: int
    amount: int
    created_at: datetime

    class Config:
        from_attributes = True


class GoalResponse(BaseModel):
    id: int
    user_id: int
    name: str
    target_amount: int
    saved_amount: int
    deadline: Optional[date] = None
    status: str
    created_at: datetime
    percentage: float = 0.0

    class Config:
        from_attributes = True


class GoalDetailResponse(GoalResponse):
    entries: List[GoalEntryResponse] = []
