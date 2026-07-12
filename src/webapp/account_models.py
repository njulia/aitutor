from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field

class StudentCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    year_group: int = Field(ge=1, le=6)
    age: int = Field(ge=5, le=12)

class StudentUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    year_group: Optional[int] = Field(default=None, ge=1, le=6)
    age: Optional[int] = Field(default=None, ge=5, le=12)
    is_active: Optional[bool] = None

class AccountSubscriptionRequest(BaseModel):
    email: str
    plan: str = Field(min_length=1, max_length=80)
    status: str = 'active'
    duration_days: int = Field(default=30, ge=1, le=3660)
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
