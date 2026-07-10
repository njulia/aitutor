from src.webapp.email_service import send_support_reply


def test_email_is_skipped_without_smtp(monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_FROM", raising=False)
    status, error = send_support_reply(
        recipient="parent@example.com",
        original_subject="Question",
        original_message="Hello",
        reply="Reply",
        admin_name="Support",
    )
    assert status == "skipped"
    assert "SMTP" in error
