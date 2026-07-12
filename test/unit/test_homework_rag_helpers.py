from __future__ import annotations

import importlib


def test_doc_ids_do_not_collide():
    rag = importlib.import_module("src.homework_rag")
    ids = {rag._new_doc_id() for _ in range(20_000)}
    assert len(ids) == 20_000


def test_k_is_bounded():
    rag = importlib.import_module("src.homework_rag")
    assert rag._bounded_k(-5) == 1
    assert rag._bounded_k(10**9) == rag.MAX_QUERY_RESULTS
