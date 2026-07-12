from src.webapp.prompt_budget import budget_review_inputs, compact_text, stable_cache_key


def test_prompt_budget_limits_large_inputs():
    result = budget_review_inputs("Q" * 50_000, "A" * 50_000, {"year_group": 3, "secret": "no"}, "R" * 50_000)
    assert len(result["homework_content"]) <= 12_000
    assert len(result["student_answers"]) <= 8_000
    assert len(result["review_feedback"]) <= 3_000
    assert "secret" not in result["profile"]


def test_cache_key_uses_complete_content():
    prefix = "a" * 500
    assert stable_cache_key("review", prefix + "x") != stable_cache_key("review", prefix + "y")
