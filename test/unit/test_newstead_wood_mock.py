from urllib.parse import urlparse

import pytest

from src import elevenplus_mock_exams as mocks

pytestmark = pytest.mark.unit


def test_newstead_wood_mock_matches_public_selection_test_format() -> None:
    exam = mocks.EXAMS["newstead-wood-11plus-1"]
    assert exam["school"] == "Newstead Wood School"
    assert exam["category"] == "school_target"
    assert exam["duration_minutes"] == 90
    assert len(exam["question_ids"]) == 48
    assert exam["question_ids"][:24] == tuple(f"v{i:02d}" for i in range(33, 57))
    assert exam["question_ids"][24:] == tuple(f"n{i:02d}" for i in range(33, 57))
    assert exam["source_ids"] == ("dfe-primary", "newstead-wood-2027", "gl-11plus-free-materials")


def test_newstead_wood_sources_are_public_https_pages() -> None:
    for source_id in mocks.EXAMS["newstead-wood-11plus-1"]["source_ids"]:
        source = mocks.PUBLIC_SOURCES[source_id]
        parsed = urlparse(source["url"])
        assert parsed.scheme == "https"
        assert parsed.netloc in {"www.newsteadwood.co.uk", "11plus.gl-assessment.co.uk", "www.gov.uk"}


def test_newstead_wood_catalogue_has_no_answers() -> None:
    item = next(x for x in mocks.mock_exam_catalogue(has_mock_access=True)["exams"] if x["id"] == "newstead-wood-11plus-1")
    assert item["available"] is True
    assert item["question_count"] == 48
    assert item["subject_counts"] == {"Verbal Reasoning": 24, "Non-Verbal Reasoning": 24}
    assert "answer" not in item
    assert "explanation" not in item
