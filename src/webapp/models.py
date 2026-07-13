from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field

class ProfileRequest(BaseModel):
    profile: dict = Field(default_factory=dict)
    subjects: list = Field(default_factory=list, max_length=12)
    quick_select: bool = False
    year: Optional[int] = None
    student_id: Optional[str] = None
    is_eleven_plus: bool = False
    mode: Optional[str] = "homework"


class ReviewRequest(BaseModel):
    homework: str = Field(min_length=1, max_length=50_000)
    answers: str = Field(min_length=1, max_length=30_000)
    subject: str = Field(default="Maths", min_length=1, max_length=80)
    profile: Optional[dict] = None
    session_id: Optional[str] = None
    is_tutor_mode: Optional[bool] = False  # Added for tutor mode review
    from_rag: Optional[bool] = False  # Whether the question came from RAG (free)
    homework_doc_id: Optional[str] = None
    question_index: Optional[int] = Field(default=None, ge=0)
    is_eleven_plus: bool = False


class ExplainDeepRequest(BaseModel):
    homework: str = Field(min_length=1, max_length=50_000)
    answers: str = Field(min_length=1, max_length=30_000)
    subject: str = Field(default="Maths", min_length=1, max_length=80)
    profile: Optional[dict] = None
    review_feedback: Optional[str] = Field(default=None, max_length=20_000)
    from_rag: Optional[bool] = False


class ImprovePracticeRequest(BaseModel):
    homework: str = Field(min_length=1, max_length=50_000)
    answers: str = Field(min_length=1, max_length=30_000)
    subject: str = Field(default="Maths", min_length=1, max_length=80)
    profile: Optional[dict] = None
    review_feedback: Optional[str] = Field(default=None, max_length=20_000)
    from_rag: Optional[bool] = False


class PhotoRequest(BaseModel):
    photo: str = Field(min_length=1, max_length=24_000_000)


class SessionUpdateRequest(BaseModel):
    homework: Optional[list] = None
    profile: Optional[dict] = None
    student_answers: Optional[str] = None
    doc_id: Optional[str] = None
    year_group: Optional[int] = None
    subject: Optional[str] = None


class FeedbackRequest(BaseModel):
    trace_id: Optional[str] = None
    score: float = Field(..., description="评分: 1.0 = thumbs up, 0.0 = thumbs down")
    name: str = Field(default="user_feedback", description="评分类型")
    comment: Optional[str] = Field(default=None, max_length=1000, description="可选文字反馈")


class AdminUserCreateRequest(BaseModel):
    """管理员创建学生请求"""
    name: str
    year_group: int = 3
    age: int = 7


class AdminSubscriptionCreateRequest(BaseModel):
    email: str
    name: str
    duration: str
    plan: Optional[str] = "homework_monthly"


class AdminUserUpdateRequest(BaseModel):
    name: Optional[str] = None
    year_group: Optional[int] = None
    age: Optional[int] = None
    is_active: Optional[bool] = None


class SubscriptionRequest(BaseModel):
    email: str
    name: str
    duration: str


class AuthRequest(BaseModel):
    username: Optional[str] = Field(default=None, max_length=254)
    email: Optional[str] = Field(default=None, max_length=254)
    password: str = Field(min_length=1, max_length=256)

    def get_username(self) -> str:
        """Get username from either username or email field"""
        return (self.username or self.email or "").strip()
