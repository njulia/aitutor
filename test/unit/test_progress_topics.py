def test_extract_topic_from_homework_set_title():
    from src.progress_db import _extract_topic_from_activity_title
    assert _extract_topic_from_activity_title("Maths Homework - Year 3 - Number Bonds (Set 999)", "Maths") == "Number Bonds"

def test_extract_topic_from_practice_set_title():
    from src.progress_db import _extract_topic_from_activity_title
    assert _extract_topic_from_activity_title("11+ Practice - Year 5 - Verbal Reasoning (Set 12)", "11+") == "Verbal Reasoning"

def test_missing_topic_returns_empty():
    from src.progress_db import _extract_topic_from_activity_title
    assert _extract_topic_from_activity_title("1. What is 2 + 2?", "Maths") == ""
