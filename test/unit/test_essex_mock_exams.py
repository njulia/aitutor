from pathlib import Path


def test_essex_mock_catalogue_and_seo_content():
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from src.elevenplus_mock_exams import EXAMS

    expected = {
        "essex-csse-11plus-2",
        "essex-csse-11plus-3",
        "colchester-essex-11plus-1",
        "southend-westcliff-essex-11plus-1",
        "chelmsford-essex-11plus-2",
    }
    assert expected.issubset(EXAMS)
    for exam_id in expected:
        exam = EXAMS[exam_id]
        assert exam["category"] == "school_target"
        assert exam["is_free"] is False
        assert exam["question_ids"]
        assert "csse-2027" in exam["source_ids"] or "cchs-fsce-2027" in exam["source_ids"]

    html = Path(__file__).resolve().parents[2] / "static" / "elevenplus-mock-exams.html"
    content = html.read_text(encoding="utf-8")
    assert "11 Plus Mock Exams Essex" in content
    assert "Essex 11+ mock exam" in content
    assert "Colchester" in content
    assert "Southend" in content
    assert "Westcliff" in content
    assert "Chelmsford" in content
