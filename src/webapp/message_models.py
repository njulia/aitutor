"""Request models for the user message and admin reply feature."""
import re
from typing import Optional
from pydantic import BaseModel, Field, field_validator

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class UserMessageCreateRequest(BaseModel):
    subject: str = Field(min_length=2, max_length=160)
    message: str = Field(min_length=2, max_length=10000)
    email: Optional[str] = Field(default=None, max_length=254)
    category: str = Field(default="general", max_length=50)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: Optional[str]) -> Optional[str]:
        if value is None or not value.strip():
            return None
        value = value.strip().lower()
        if not _EMAIL_RE.match(value):
            raise ValueError("Invalid email address")
        return value


class AdminMessageReplyRequest(BaseModel):
    reply: str = Field(min_length=2, max_length=10000)
    admin_name: str = Field(default="Homework Magic Support", max_length=120)
    send_email: bool = True


class AdminMessageStatusRequest(BaseModel):
    status: str = Field(pattern=r"^(open|pending|replied|closed)$")
