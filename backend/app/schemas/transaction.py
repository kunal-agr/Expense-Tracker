from datetime import date as py_date, datetime
from pydantic import BaseModel, Field, field_validator


class TransactionBase(BaseModel):
    type: str = Field(pattern="^(income|expense)$")
    amount: int = Field(ge=1, description="Amount in whole rupees")
    date: py_date
    category_id: int
    subcategory_id: int | None = None
    payment_method: str = Field(pattern="^(UPI|Card|Cash)$")
    note: str | None = Field(default=None, max_length=500)

    @field_validator("date")
    @classmethod
    def validate_date_not_future(cls, v: py_date) -> py_date:
        today = py_date.today()
        if v > today:
            raise ValueError("Transaction date cannot be in the future (today or past dates only).")
        return v


class TransactionCreate(TransactionBase):
    pass


class TransactionUpdate(BaseModel):
    amount: int | None = Field(default=None, ge=1)
    date: py_date | None = None
    category_id: int | None = None
    subcategory_id: int | None = None
    payment_method: str | None = Field(default=None, pattern="^(UPI|Card|Cash)$")
    note: str | None = Field(default=None, max_length=500)

    @field_validator("date")
    @classmethod
    def validate_date_not_future(cls, v: py_date | None) -> py_date | None:
        if v is not None and v > py_date.today():
            raise ValueError("Transaction date cannot be in the future (today or past dates only).")
        return v


class TransactionResponse(BaseModel):
    id: int
    user_id: int
    wallet_id: int
    type: str
    amount: int
    date: py_date
    category_id: int
    category_name: str | None = None
    subcategory_id: int | None = None
    subcategory_name: str | None = None
    payment_method: str
    note: str | None = None
    source: str
    read_only: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TransactionListResponse(BaseModel):
    items: list[TransactionResponse]
    total: int
    page: int
    limit: int
    pages: int
