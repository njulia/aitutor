"""Concurrency coverage for saved 11+ mock explanations."""
from __future__ import annotations

import asyncio

from src.webapp import mock_exam_routes


def test_same_mock_question_uses_one_ai_worker_while_other_requests_wait(monkeypatch) -> None:
    calls = []

    async def fake_run_blocking(_func, *args, **kwargs):
        calls.append((args, kwargs))
        await asyncio.sleep(0.01)
        return ("## How to solve it\nUse the clues.", False)

    monkeypatch.setattr(mock_exam_routes, "run_blocking", fake_run_blocking)

    async def run_requests():
        return await asyncio.gather(*[
            mock_exam_routes._load_or_create_mock_explanation_once(
                fingerprint="the-same-reviewed-question",
                fallback="## How to solve it\nUse a safe fallback.",
                llm_client=object(),
                prompt="Question prompt",
                exam_id="mock-1",
                question_id="q1",
                question={"subject": "Maths", "topic": "Fractions"},
            )
            for _ in range(12)
        ])

    outcomes = asyncio.run(run_requests())

    assert len(calls) == 1
    assert outcomes == [("## How to solve it\nUse the clues.", False)] * 12
