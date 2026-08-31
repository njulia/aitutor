from __future__ import annotations

from fastapi.testclient import TestClient

from test.conftest import register_or_login


def test_admin_delete_removes_auth_learner_and_subscription(app_module, unique_email):
    # Keep independent cookies for the target user and administrator.
    target = TestClient(app_module.app, base_url="http://testserver")
    admin = TestClient(app_module.app, base_url="http://testserver")
    try:
        register_or_login(target, unique_email)
        register_or_login(admin, "admin@example.com")

        from src.webapp.account_store import ensure_account, create_subscription, get_account_by_email, get_active_subscription
        account = ensure_account(unique_email)
        create_subscription(account["id"], "homework_monthly", "canceled", 30)
        assert get_account_by_email(unique_email) is not None

        response = admin.delete(f"/api/admin/auth-users/{unique_email}")
        assert response.status_code == 200, response.text
        assert response.json()["auth_deleted"] is True
        assert response.json()["account_deleted"] is True

        from src.progress_db import get_user_by_username
        assert get_user_by_username(unique_email) is None
        assert get_account_by_email(unique_email) is None
        assert get_active_subscription(account["id"]) is None
        # Existing target session is revoked by the deletion workflow.
        assert target.get("/api/account").status_code == 401
    finally:
        target.close()
        admin.close()
