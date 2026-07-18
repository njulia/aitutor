from __future__ import annotations

import uuid

from src.progress_db import create_user, verify_user_credentials
from src.webapp.password_backend import account_exists, set_account_password


def test_password_backend_updates_shared_account_store():
    email = f"reset-{uuid.uuid4().hex[:12]}@example.com"
    old_password = "OldPassword123!"
    new_password = "NewPassword456!"

    create_user(email, old_password)
    assert account_exists(email) is True
    assert verify_user_credentials(email, old_password) is True

    assert set_account_password(email, new_password) is True
    assert verify_user_credentials(email, old_password) is False
    assert verify_user_credentials(email, new_password) is True
