from __future__ import annotations

import uuid

import pytest

from src.webapp import review_service


class RecordingLLM:
    provider = "api"
    model = "default-model"

    def __init__(self) -> None:
        self.models = []
        self.prompts = []

    def complete(self, messages, temperature=None, max_tokens=None, model=None):
        self.models.append(model)
        self.prompts.append(messages[0]["content"])
        return (
            "## Score\n\n**1/2**\n\n"
            "## What You Did Well\n\n- Question 1 is correct.\n\n"
            "## What to Improve\n\n- Question 2 needs another look.\n\n"
            "## Keep Going\n\nYou made a good start."
        )


def test_uploaded_review_uses_dedicated_fast_path_without_method_store(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        review_service,
        "_prepare_solution_methods",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Uploaded basic marking must not query solution methods")
        ),
    )
    llm = RecordingLLM()
    result = review_service.review_homework(
        f"1. What is 3 + 4?\n2. What is 9 - 3? Ref {uuid.uuid4().hex}",
        "1. 7\n2. 5",
        "Maths",
        {"year_group": 2, "age": 6},
        uploaded_work=True,
        llm_client=llm,
    )

    assert result["success"] is True
    assert result["model_tier"] == "flash"
    assert result["score"] == 1
    assert result["max_score"] == 2
    assert result["solution_methods"] == []
    assert llm.models == [review_service.QUICK_REVIEW_MODEL]
    assert "reviewing an uploaded worksheet" in llm.prompts[0]
    assert "Pupil answers:" in llm.prompts[0]


def test_failed_upload_processing_always_removes_temporary_file(
    tmp_path, monkeypatch
) -> None:
    import web_app

    path = tmp_path / "broken.pdf"
    path.write_bytes(b"%PDF-broken")
    monkeypatch.setattr(
        web_app,
        "read_pdf_file",
        lambda _path: (_ for _ in ()).throw(ValueError("broken PDF")),
    )

    with pytest.raises(ValueError, match="broken PDF"):
        web_app.process_uploaded_file(str(path))
    assert not path.exists()
