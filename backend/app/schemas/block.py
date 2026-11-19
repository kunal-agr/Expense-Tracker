from datetime import datetime
from pydantic import BaseModel, Field


class BlockCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)


class BlockResponse(BaseModel):
    id: int
    blocked_id: int
    blocked_username: str
    created_at: datetime

    class Config:
        from_attributes = True
