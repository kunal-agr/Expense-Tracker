from datetime import datetime
from pydantic import BaseModel, Field


class OpeningBalanceRequest(BaseModel):
    opening_balance: int = Field(ge=100, description="Opening balance in whole rupees (minimum 100)")


class WalletResponse(BaseModel):
    id: int
    user_id: int
    opening_balance: int
    current_balance: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
