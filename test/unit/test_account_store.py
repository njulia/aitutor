from datetime import datetime, timedelta, UTC

from src.webapp import account_store


def use_temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(account_store, "DB_PATH", str(tmp_path / "accounts.db"))
    account_store.init_account_db()


def test_account_gets_default_student(tmp_path, monkeypatch):
    use_temp_db(tmp_path, monkeypatch)
    account = account_store.ensure_account("Parent@Example.com")
    student = account_store.ensure_default_student(account["id"])
    assert account["email"] == "parent@example.com"
    assert student["account_id"] == account["id"]
    assert len(account_store.list_students(account["id"])) == 1


def test_multiple_students_belong_to_one_account(tmp_path, monkeypatch):
    use_temp_db(tmp_path, monkeypatch)
    account = account_store.ensure_account("parent@example.com")
    first = account_store.create_student(account["id"], "Tom", 3, 7)
    second = account_store.create_student(account["id"], "Lucy", 5, 9)
    assert account_store.student_belongs_to_account(first["id"], account["id"])
    assert account_store.student_belongs_to_account(second["id"], account["id"])
    assert len(account_store.list_students(account["id"])) == 2


def test_student_cannot_be_accessed_by_other_account(tmp_path, monkeypatch):
    use_temp_db(tmp_path, monkeypatch)
    owner = account_store.ensure_account("owner@example.com")
    other = account_store.ensure_account("other@example.com")
    student = account_store.create_student(owner["id"], "Child", 2, 6)
    assert not account_store.student_belongs_to_account(student["id"], other["id"])


def test_subscription_is_shared_by_all_account_students(tmp_path, monkeypatch):
    use_temp_db(tmp_path, monkeypatch)
    account = account_store.ensure_account("parent@example.com")
    account_store.create_student(account["id"], "Tom", 3, 7)
    account_store.create_student(account["id"], "Lucy", 5, 9)
    account_store.create_subscription(account["id"], "family", "active", 30)
    assert account_store.account_has_active_subscription("parent@example.com")
    assert account_store.get_active_subscription(account["id"])["plan"] == "family"


def test_expired_subscription_is_not_active(tmp_path, monkeypatch):
    use_temp_db(tmp_path, monkeypatch)
    account = account_store.ensure_account("parent@example.com")
    sub = account_store.create_subscription(account["id"], "premium", "active", 30)
    expired = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    with account_store._db() as conn:
        conn.execute("UPDATE account_subscriptions SET expires_at=? WHERE id=?", (expired, sub["id"]))
    assert not account_store.account_has_active_subscription("parent@example.com")
