import pytest
from pydantic import ValidationError
from src.webapp.message_models import UserMessageCreateRequest, AdminMessageStatusRequest


def test_email_is_normalised():
    model = UserMessageCreateRequest(subject="Hello", message="Please help", email=" Parent@Example.com ")
    assert model.email == "parent@example.com"


def test_invalid_email_is_rejected():
    with pytest.raises(ValidationError):
        UserMessageCreateRequest(subject="Hello", message="Please help", email="not-an-email")


def test_message_status_allowlist():
    assert AdminMessageStatusRequest(status="closed").status == "closed"
    with pytest.raises(ValidationError):
        AdminMessageStatusRequest(status="deleted")
