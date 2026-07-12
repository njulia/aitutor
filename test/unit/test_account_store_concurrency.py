from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import src.webapp.account_store as store


def test_concurrent_lazy_migration_creates_one_account_and_one_default_student(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "accounts.db"))
    monkeypatch.setattr(store, "_INITIALISED_PATH", None)

    def create(_index: int):
        account = store.ensure_account("Parent@Example.com")
        student = store.ensure_default_student(account["id"])
        return account["id"], student["id"]

    with ThreadPoolExecutor(max_workers=12) as pool:
        values = list(pool.map(create, range(40)))

    assert len({account_id for account_id, _ in values}) == 1
    assert len({student_id for _, student_id in values}) == 1
    account = store.get_account_by_email("parent@example.com")
    students = store.list_students(account["id"])
    assert len(students) == 1
    assert students[0]["is_default"] == 1


def test_student_validation(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "accounts.db"))
    monkeypatch.setattr(store, "_INITIALISED_PATH", None)
    account = store.ensure_account("parent@example.com")
    for year, age in ((0, 7), (7, 7), (3, 4), (3, 13)):
        try:
            store.create_student(account["id"], "Child", year, age)
        except ValueError:
            pass
        else:
            raise AssertionError((year, age))
