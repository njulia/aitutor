def test_extract_topic_from_homework_set_title():
    from src.progress_db import _extract_topic_from_activity_title
    assert _extract_topic_from_activity_title("Maths Homework - Year 3 - Number Bonds (Set 999)", "Maths") == "Number Bonds"

def test_extract_topic_from_practice_set_title():
    from src.progress_db import _extract_topic_from_activity_title
    assert _extract_topic_from_activity_title("11+ Practice - Year 5 - Verbal Reasoning (Set 12)", "11+") == "Verbal Reasoning"

def test_exact_year_1_simple_addition_title():
    from src.progress_db import _extract_topic_from_activity_title
    assert _extract_topic_from_activity_title(
        "Maths Homework - Year 1 - Simple Addition (Set 555)", "Maths"
    ) == "Simple Addition"


def test_typographic_dash_and_markdown_heading_are_supported():
    from src.progress_db import _extract_topic_from_activity_title
    assert _extract_topic_from_activity_title(
        "## Maths Homework – Year 1 – Simple Addition (Set 555)", "Maths"
    ) == "Simple Addition"


def test_subject_is_never_used_as_topic():
    from src.progress_db import _extract_topic_from_activity_title
    assert _extract_topic_from_activity_title(
        "Maths Homework - Year 1 - Maths (Set 555)", "Maths"
    ) == ""


def test_missing_topic_returns_empty():
    from src.progress_db import _extract_topic_from_activity_title
    assert _extract_topic_from_activity_title("1. What is 2 + 2?", "Maths") == ""
