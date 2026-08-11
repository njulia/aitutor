from __future__ import annotations

from datetime import UTC, datetime, timedelta

from src.webapp.capybara_store import CapybaraStore


def test_new_student_starts_as_cute_baby(tmp_path):
    store = CapybaraStore(f"sqlite+pysqlite:///{tmp_path / 'pet.db'}")
    state = store.status(
        account_id="account_1", student_id="student_1",
        daily_goal_completed=False, today="2026-08-11",
    )
    assert state["alive"] is True
    assert state["generation"] == 1
    assert state["growth"]["stage"] == 1
    assert state["growth"]["cute"] is True
    assert state["fruit"] == "apple"


def test_playtime_requires_daily_goal_and_does_not_touch_rewards(tmp_path):
    store = CapybaraStore(f"sqlite+pysqlite:///{tmp_path / 'pet.db'}")
    try:
        store.act(
            account_id="account_1", student_id="student_1", activity="play",
            daily_goal_completed=False, today="2026-08-11",
        )
    except PermissionError as exc:
        assert "Daily Goal" in str(exc)
    else:
        raise AssertionError("play should be locked before the Daily Goal")

    state = store.act(
        account_id="account_1", student_id="student_1", activity="play",
        daily_goal_completed=True, today="2026-08-11",
    )
    assert state["played_today"] is True
    assert state["no_xp_change"] is True
    assert state["no_gift_points_change"] is True


def test_missing_play_after_completed_goal_starts_next_visit_dead(tmp_path):
    store = CapybaraStore(f"sqlite+pysqlite:///{tmp_path / 'pet.db'}")
    state = store.status(
        account_id="account_1", student_id="student_1",
        daily_goal_completed=True, today="2026-08-11",
    )
    assert state["alive"] is True
    state = store.status(
        account_id="account_1", student_id="student_1",
        daily_goal_completed=False, today="2026-08-12",
    )
    assert state["alive"] is False
    assert state["deceased_at"]


def test_dead_pet_is_replaced_by_new_baby_generation(tmp_path):
    store = CapybaraStore(f"sqlite+pysqlite:///{tmp_path / 'pet.db'}")
    store.status(account_id="a", student_id="s", daily_goal_completed=True, today="2026-08-11")
    store.status(account_id="a", student_id="s", daily_goal_completed=False, today="2026-08-12")
    state = store.adopt_new_baby(account_id="a", student_id="s", daily_goal_completed=False, today="2026-08-12")
    assert state["alive"] is True
    assert state["generation"] == 2
    assert state["growth"]["stage"] == 1
    assert state["growth"]["care_points"] == 0
    assert state["fruit"] == "apple"


def test_fruit_choices_are_persistent_and_child_safe(tmp_path):
    store = CapybaraStore(f"sqlite+pysqlite:///{tmp_path / 'pet.db'}")
    state = store.set_fruit(
        account_id="a", student_id="s", fruit="strawberry",
        daily_goal_completed=True, today="2026-08-11",
    )
    assert state["fruit"] == "strawberry"
    assert state["fruit_info"]["emoji"] == "🍓"
