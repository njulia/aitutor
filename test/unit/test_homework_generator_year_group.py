import pytest
from unittest.mock import MagicMock
import src.homework_generator as generator
from src.webapp.homework_assignment_store import HomeworkAssignmentStore

@pytest.fixture
def mock_assignment_store(monkeypatch, tmp_path):
    store = HomeworkAssignmentStore(f"sqlite+pysqlite:///{tmp_path / 'test_assignments.db'}")
    monkeypatch.setattr(generator, "get_assignment_store", lambda: store)
    return store

def test_math_year_group_respects_profile(monkeypatch, mock_assignment_store):
    # Mock search_homework_by_metadata to capture calls
    mock_search = MagicMock(return_value=[])
    monkeypatch.setattr(generator, "search_homework_by_metadata", mock_search)
    monkeypatch.setattr(generator, "get_student_previous_topics", lambda *_: [])
    
    llm = MagicMock()
    llm.complete.return_value = "Mocked Homework"
    
    profile = {"student_id": "student_y2", "year_group": 2, "age": 6}
    subject = "Maths"
    
    # Run the generator
    generator.generate_homework_for_subject(profile, subject, llm, is_eleven_plus=False)
    
    # Verify that search_homework_by_metadata was called with year_group=2
    args, kwargs = mock_search.call_args
    assert kwargs["year_group"] == 2
    assert kwargs["subject"] == "Maths"

def test_math_year_group_forces_6_for_11plus(monkeypatch, mock_assignment_store):
    # Mock elevenplus_search_homework_by_metadata to capture calls
    mock_search = MagicMock(return_value=[])
    monkeypatch.setattr(generator, "elevenplus_search_homework_by_metadata", mock_search)
    monkeypatch.setattr(generator, "elevenplus_get_student_previous_topics", lambda *_: [])
    
    llm = MagicMock()
    llm.complete.return_value = "Mocked 11+ Homework"
    
    # Profile says year 5, but for 11+ it should be forced to 6
    profile = {"student_id": "student_y5", "year_group": 5, "age": 9}
    subject = "Maths"
    
    # Run the generator
    generator.generate_homework_for_subject(profile, subject, llm, is_eleven_plus=True)
    
    # Verify that elevenplus_search_homework_by_metadata was called with year_group=6
    args, kwargs = mock_search.call_args
    assert kwargs["year_group"] == 6
    assert kwargs["subject"] == "Maths"
