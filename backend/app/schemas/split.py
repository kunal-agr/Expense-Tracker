from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class ParticipantInput(BaseModel):
    username: str
    amount: Optional[int] = Field(default=None, ge=0, description="Rupee amount for exact split")
    percentage: Optional[float] = Field(default=None, ge=0, le=100, description="Percentage for percentage split")
    shares: Optional[int] = Field(default=None, ge=1, description="Shares weight for shares split")


class SplitCreate(BaseModel):
    total_amount: int = Field(ge=1, description="Total bill amount in whole rupees")
    split_type: str = Field(pattern="^(exact|percentage|shares)$")
    note: Optional[str] = Field(default=None, max_length=500)
    group_id: Optional[int] = None
    category_id: Optional[int] = None
    payment_method: str = Field(default="UPI", pattern="^(UPI|Card|Cash)$")
    participants: List[ParticipantInput] = []
    remainder_bearer_username: Optional[str] = None


class SplitUpdate(BaseModel):
    note: Optional[str] = Field(default=None, max_length=500)
    participants: Optional[List[ParticipantInput]] = None
    remainder_bearer_username: Optional[str] = None


class SplitParticipantResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    username: str
    share_amount: int
    status: str  # 'pending', 'accepted', 'rejected', 'expired'
    responded_at: Optional[datetime] = None
    is_payer: bool = False

    class Config:
        from_attributes = True


class SplitResponse(BaseModel):
    id: int
    payer_id: int
    payer_username: str
    group_id: Optional[int] = None
    group_name: Optional[str] = None
    total_amount: int
    split_type: str
    note: Optional[str] = None
    status: str  # 'pending', 'locked', 'cancelled'
    remainder_bearer_username: Optional[str] = None
    created_at: datetime
    expires_at: datetime
    locked_at: Optional[datetime] = None
    participants: List[SplitParticipantResponse] = []
    user_share_status: Optional[str] = None
    user_share_amount: Optional[int] = None

    class Config:
        from_attributes = True
