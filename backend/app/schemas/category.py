from datetime import datetime
from pydantic import BaseModel, Field


class SubcategoryResponse(BaseModel):
    id: int
    user_id: int
    parent_id: int | None
    name: str
    type: str
    is_protected: bool
    created_at: datetime

    class Config:
        from_attributes = True


class CategoryResponse(BaseModel):
    id: int
    user_id: int
    parent_id: int | None
    name: str
    type: str
    is_protected: bool
    created_at: datetime
    subcategories: list[SubcategoryResponse] = []

    class Config:
        from_attributes = True


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    type: str = Field(pattern="^(income|expense)$")
    parent_id: int | None = None


class CategoryUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
