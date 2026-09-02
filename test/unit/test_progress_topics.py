from src.progress_db import get_topic_progress, save_homework_session


def test_topic_progress_keeps_topic_separate_from_subject(tmp_path, monkeypatch):
    db = tmp_path / "progress.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db}")

    # progress_db is imported before the test environment is configured in some
    # suites, so use its existing engine configuration where possible.
    save_homework_session(
        student_id="topic_test_student",
        subject="Maths",
        year_group=5,
        homework_content="Practise fractions and equivalent fractions",
        student_answers="",
        score=8,
        max_score=10,
        topic="Fractions",
    )
    rows = get_topic_progress("topic_test_student")
    assert rows
    assert rows[0]["subject"] == "Maths"
    assert rows[0]["topic"] == "Fractions"
    assert rows[0]["topic"] != rows[0]["subject"]
