"""Validation models for parent/guardian support messages."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class MessageCreate(BaseModel):
    category: str = Field(default="general", max_length=40)
    subject: str = Field(min_length=2, max_length=160)
    message: str = Field(min_length=2, max_length=5000)
    contact_email: Optional[str] = Field(default=None, max_length=254)


class AdminReplyCreate(BaseModel):
    reply: str = Field(min_length=2, max_length=5000)
    send_email: bool = True


class StatusChange(BaseModel):
    status: str = Field(min_length=2, max_length=20)
