from pathlib import Path

from src.webapp.password_reset_store import PasswordResetStore


def test_token_is_single_use(tmp_path: Path):
    store = PasswordResetStore(str(tmp_path), db_path=str(tmp_path / "reset.db"))
    token, _ = store.create_token("parent@example.com")
    assert store.is_valid(token)
    assert store.consume(token) == "parent@example.com"
    assert not store.is_valid(token)
    assert store.consume(token) is None


def test_new_token_invalidates_previous_token(tmp_path: Path):
    store = PasswordResetStore(str(tmp_path), db_path=str(tmp_path / "reset.db"))
    old_token, _ = store.create_token("parent@example.com")
    new_token, _ = store.create_token("parent@example.com")
    assert not store.is_valid(old_token)
    assert store.is_valid(new_token)


def test_rate_limit_does_not_store_raw_email_in_request_log(tmp_path: Path):
    store = PasswordResetStore(str(tmp_path), db_path=str(tmp_path / "reset.db"))
    assert store.record_request_if_allowed("parent@example.com", "client-hash")
    with store._connection() as conn:
        row = conn.execute("SELECT email_hash FROM password_reset_requests").fetchone()
    assert row[0] != "parent@example.com"
