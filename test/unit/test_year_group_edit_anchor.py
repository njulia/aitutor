from __future__ import annotations

from datetime import UTC, datetime

from src.webapp.account_store import adjust_student_for_academic_year


def test_parent_selected_year_is_authoritative_for_current_academic_year() -> None:
    # Simulates a child created last academic year and explicitly edited on
    # 2 September 2026. The selected Year 3 must not immediately become Year 4.
    student = {
        "id": "stu_test",
        "name": "Ava",
        "year_group": 3,
        "age": 8,
        "created_at": datetime(2025, 6, 1, tzinfo=UTC),
        "year_group_set_at": datetime(2026, 9, 2, tzinfo=UTC),
    }
    adjusted = adjust_student_for_academic_year(student)
    assert adjusted["year_group"] == 3
    assert adjusted["age"] == 8
