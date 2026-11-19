from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class GroupUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class GroupInviteRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)


class GroupMemberResponse(BaseModel):
    id: int
    user_id: int
    username: str
    joined_at: Optional[datetime] = None
    status: str  # 'invited', 'active'
    is_creator: bool = False

    class Config:
        from_attributes = True


class GroupResponse(BaseModel):
    id: int
    name: str
    creator_id: Optional[int] = None
    creator_username: Optional[str] = None
    created_at: datetime
    member_count: int = 0
    user_status: str  # 'active', 'invited'

    class Config:
        from_attributes = True


class GroupDetailResponse(GroupResponse):
    members: List[GroupMemberResponse] = []
