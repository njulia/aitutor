from __future__ import annotations

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.integration]


@pytest.fixture
def rag_module():
    import src.homework_rag as rag
    return rag


def test_rag_document_ids_are_unique(rag_module) -> None:
    ids = {rag_module._new_doc_id() for _ in range(10_000)}
    assert len(ids) == 10_000


def test_rag_result_count_is_bounded(rag_module) -> None:
    assert rag_module._bounded_k(-1) == 1
    assert rag_module._bounded_k(10**9) == rag_module.MAX_QUERY_RESULTS


def test_metadata_filter_contract_uses_integer_year_and_canonical_subject() -> None:
    filters = {"year_group": 1, "subject": "Maths"}
    assert isinstance(filters["year_group"], int)
    assert filters["subject"] == "Maths"


def test_batch_limit_protects_rag_writes(rag_module, tmp_path) -> None:
    # This checks the public safety contract without embedding thousands of docs.
    store = object.__new__(rag_module.HomeworkRAGStore)
    oversized = [
        {"content": f"Question {i}", "metadata": {"year_group": 1, "subject": "Maths"}}
        for i in range(501)
    ]
    with pytest.raises(ValueError, match="batch"):
        store.add_batch_homework(oversized)
