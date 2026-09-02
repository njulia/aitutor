from sqlalchemy import create_engine

from src import progress_db


def test_mistake_bank_is_deduplicated_and_answer_is_not_exposed(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    progress_db.metadata.create_all(engine)
    monkeypatch.setattr(progress_db, "_engine", engine)

    saved = progress_db.save_mistake_questions(
        "student-1",
        [{
            "question": "What is 3/4 + 1/4?",
            "subject": "Maths",
            "topic": "Fractions, Decimals & Percentages",
            "mistake_type": "Fractions, Decimals & Percentages",
            "source_type": "topic_mastery",
            "options": [
                {"label": "A", "text": "1/2"},
                {"label": "B", "text": "1"},
                {"label": "C", "text": "2"},
                {"label": "D", "text": "3/4"},
            ],
            "correct_letter": "B",
            "correct_answer": "1",
            "explanation": "The denominators are already the same.",
        }],
    )
    assert saved == 1

    saved_again = progress_db.save_mistake_questions(
        "student-1",
        [{
            "question": "  What is 3/4 + 1/4? ",
            "subject": "Maths",
            "topic": "Fractions, Decimals & Percentages",
            "correct_letter": "B",
            "correct_answer": "1",
        }],
    )
    assert saved_again == 1

    questions = progress_db.get_mistake_questions("student-1")
    assert len(questions) == 1
    assert questions[0]["miss_count"] == 2
    assert "correct_answer" not in questions[0]
    assert "correct_letter" not in questions[0]
    assert questions[0]["options"][1]["text"] == "1"

    result = progress_db.check_mistake_question("student-1", questions[0]["id"], "B")
    assert result["success"] is True
    assert result["correct"] is True
    assert result["correct_answer"] == "1"


def test_11plus_mistake_source_classification_covers_all_learning_paths():
    from src.webapp.review_service import _mistake_source_type

    assert _mistake_source_type({"topic_mastery": True}, True) == "topic_mastery"
    assert _mistake_source_type({"plan_week": 12}, True) == "year_round"
    assert _mistake_source_type({}, True) == "11plus_practice"
