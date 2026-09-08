from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field

TxType = Literal["expense", "income"]
CategoryType = Literal["expense_category1", "income_category", "expense_category2"]

class TransactionIn(BaseModel):
    id: Optional[str] = None
    project: str = Field(min_length=1, max_length=200)
    date: str
    member: str = Field(min_length=1, max_length=100)
    type: TxType = "expense"
    category1: Optional[str] = None
    category2: Optional[str] = None
    amount_cents: int = Field(ge=0)
    note: Optional[str] = Field(default=None, max_length=1000)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    device_id: Optional[str] = None
    is_deleted: bool = False

class TransactionOut(TransactionIn):
    id: str
    created_at: str
    updated_at: str
    device_id: str
    is_deleted: bool

class CategoryIn(BaseModel):
    id: Optional[str] = None
    type: CategoryType
    name: str = Field(min_length=1, max_length=100)
    sort_order: int = 0
    is_active: bool = True

class CategoryOut(CategoryIn):
    id: str
    updated_at: str

class MemberIn(BaseModel):
    id: Optional[str] = None
    name: str = Field(min_length=1, max_length=100)
    sort_order: int = 0
    is_active: bool = True

class MemberOut(MemberIn):
    id: str
    updated_at: str

class SyncRequest(BaseModel):
    device_id: str
    changes: list[TransactionIn] = []

class AdminLogin(BaseModel):
    password: str
