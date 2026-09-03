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



def test_11plus_review_profile_keeps_topic_mastery_and_topic_metadata():
    from src.webapp import review_service

    profile = review_service._normalise_profile({
        "year_group": 6,
        "age": 11,
        "topic_mastery": True,
        "topic": "Fractions",
        "mastery_level": 3,
    })

    assert profile["topic_mastery"] is True
    assert profile["topic"] == "Fractions"
    assert profile["mastery_level"] == 3


def test_mistake_bank_groups_and_filters_by_topic(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    progress_db.metadata.create_all(engine)
    monkeypatch.setattr(progress_db, "_engine", engine)

    progress_db.save_mistake_questions("student-2", [
        {"question": "Q1", "subject": "Maths", "topic": "Fractions", "correct_answer": "A", "source_type": "mock_exam"},
        {"question": "Q2", "subject": "English", "topic": "Comprehension", "correct_answer": "B", "source_type": "topic_mastery"},
        {"question": "Q3", "subject": "Maths", "topic": "Fractions", "correct_answer": "C", "source_type": "year_round"},
    ])

    counts = progress_db.get_mistake_topic_counts("student-2")
    assert counts == [
        {"subject": "English", "topic": "Comprehension", "count": 1},
        {"subject": "Maths", "topic": "Fractions", "count": 2},
    ]
    maths = progress_db.get_mistake_questions("student-2", subject="Maths", topic="Fractions")
    assert {item["question"] for item in maths} == {"Q1", "Q3"}
