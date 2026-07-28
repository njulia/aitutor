"""Bounded request models for the family reward system."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, SecretStr


class RewardRequest(BaseModel):
    student_id: str = Field(min_length=1, max_length=80)
    reward_code: str = Field(min_length=1, max_length=100)


class DeliveryAddressRequest(BaseModel):
    recipient_name: str = Field(min_length=2, max_length=80)
    address_line1: str = Field(min_length=3, max_length=100)
    address_line2: str = Field(default="", max_length=100)
    town_city: str = Field(min_length=2, max_length=80)
    postcode: str = Field(min_length=5, max_length=10)
    country: Literal["GB"] = "GB"
    adult_recipient_confirmed: Literal[True]


class RewardDecisionRequest(BaseModel):
    decision: Literal["approve", "decline", "cancel"]
    parent_password: SecretStr = Field(min_length=1, max_length=256)
    delivery_address: DeliveryAddressRequest | None = None


class AdminGiftOrderDecisionRequest(BaseModel):
    decision: Literal["dispatch", "cancel"]
