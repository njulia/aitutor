from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

from src.webapp.session_store import SessionTooLarge, TutorSessionStore


def test_sessions_are_owner_bound_and_persistent(tmp_path):
    db = tmp_path / "sessions.db"
    first = TutorSessionStore(str(db), ttl_seconds=60)
    created = first.create("owner-a", {"subject": "Maths"})

    second = TutorSessionStore(str(db), ttl_seconds=60)
    assert second.get(created["session_id"], "owner-a")["subject"] == "Maths"
    assert second.get(created["session_id"], "owner-b") is None


def test_concurrent_updates_do_not_corrupt_json(tmp_path):
    store = TutorSessionStore(str(tmp_path / "sessions.db"), ttl_seconds=60)
    session = store.create("owner", {"counter": 0})

    def update(index: int):
        return store.update(session["session_id"], "owner", {f"value_{index}": index})

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(update, range(20)))

    result = store.get(session["session_id"], "owner")
    assert result is not None
    assert result["version"] == 21
    for index in range(20):
        assert result[f"value_{index}"] == index


def test_payload_limit(tmp_path):
    store = TutorSessionStore(str(tmp_path / "sessions.db"), max_payload_bytes=64)
    try:
        store.create("owner", {"too_big": "x" * 100})
    except SessionTooLarge:
        pass
    else:
        raise AssertionError("SessionTooLarge was not raised")
