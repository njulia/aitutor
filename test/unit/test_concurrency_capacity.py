from __future__ import annotations

import asyncio
import re
import threading
from pathlib import Path

import pytest
import requests
from fastapi import HTTPException

from src import llm_client
from src.webapp import db, runtime


def test_timed_out_ai_call_keeps_bulkhead_permit_until_thread_finishes(
    monkeypatch,
) -> None:
    previous = runtime._blocking_semaphore
    release_work = threading.Event()
    work_started = threading.Event()

    def slow_call():
        work_started.set()
        release_work.wait(timeout=2)
        return "finished"

    async def scenario() -> None:
        runtime._blocking_semaphore = asyncio.Semaphore(1)
        with pytest.raises(HTTPException) as timeout_error:
            await runtime.run_blocking(slow_call, timeout=0.02)
        assert timeout_error.value.status_code == 504
        assert work_started.is_set()

        next_call = asyncio.create_task(
            runtime.run_blocking(lambda: "next", timeout=1)
        )
        await asyncio.sleep(0.05)
        assert not next_call.done()

        release_work.set()
        assert await next_call == "next"

    try:
        asyncio.run(scenario())
    finally:
        release_work.set()
        runtime._blocking_semaphore = previous


class _Response:
    headers = {}

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(
                f"status {self.status_code}",
                response=self,
            )

    def json(self):
        return {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {},
        }


class _RetryingSession:
    def __init__(self) -> None:
        self.calls = 0

    def post(self, *_args, **_kwargs):
        self.calls += 1
        return _Response(503 if self.calls == 1 else 200)


def test_llm_client_retries_transient_failure_and_reuses_session(
    monkeypatch,
) -> None:
    session = _RetryingSession()
    monkeypatch.setattr(llm_client, "MAX_RETRIES", 1)
    monkeypatch.setattr(llm_client.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        llm_client.LLMClient,
        "_http_session",
        staticmethod(lambda: session),
    )
    client = llm_client.LLMClient(
        provider="api",
        model="test-model",
        api_key="test-key",
        api_base="https://provider.invalid/v1",
    )

    assert client.complete([{"role": "user", "content": "hello"}]) == "ok"
    assert session.calls == 2


def test_request_local_detail_clients_share_vertex_transport(monkeypatch) -> None:
    sentinel = object()
    key = ("test-project", "europe-west2")
    monkeypatch.setattr(llm_client, "_VERTEX_CLIENTS", {key: sentinel})
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", key[0])
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", key[1])
    monkeypatch.setenv("DETAIL_REVIEW_PROVIDER", "vertex_ai")
    monkeypatch.setattr(llm_client, "DEEPSEEK_API_KEY", "test-key")

    root = llm_client.LLMClient(provider="deepseek")
    first = root.with_model(llm_client.DETAIL_REVIEW_MODEL)
    second = root.with_model(llm_client.DETAIL_REVIEW_MODEL)

    assert first._get_vertex_client() is sentinel
    assert second._get_vertex_client() is sentinel


def test_database_engine_is_shared_per_url(tmp_path) -> None:
    url = f"sqlite+pysqlite:///{tmp_path / 'shared.db'}"
    assert db.get_engine(url) is db.get_engine(url)


def test_cloud_run_defaults_offer_more_than_one_thousand_request_slots() -> None:
    source = Path("deploy/deploy_gcp.sh").read_text(encoding="utf-8")

    concurrency = int(
        re.search(r'CLOUD_RUN_CONCURRENCY="\$\{CLOUD_RUN_CONCURRENCY:-(\d+)\}"', source).group(1)
    )
    maximum = int(
        re.search(r'CLOUD_RUN_MAX_INSTANCES="\$\{CLOUD_RUN_MAX_INSTANCES:-(\d+)\}"', source).group(1)
    )
    assert concurrency * maximum >= 1_000

    environment = Path("deploy/cloud-run.env.yaml.example").read_text(
        encoding="utf-8"
    )
    assert 'MAX_AI_CONCURRENCY: "20"' in environment
    assert 'MAX_PROVIDER_CONCURRENCY: "24"' in environment
    assert 20 * maximum > 1_000
    assert 'DB_POOL_SIZE: "3"' in environment
    assert 'WEB_CONCURRENCY: "1"' in environment
