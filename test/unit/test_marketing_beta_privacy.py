"""Contracts for the small parent beta and aggregate-only measurement."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.webapp import account_store
from src.webapp.privacy_metrics import PrivacyMetricsStore

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]


def test_aggregate_metrics_schema_contains_no_user_or_child_identifiers(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("MARKETING_METRICS_ENABLED", "true")
    monkeypatch.setenv("VOICE_METRICS_ENABLED", "true")
    store = PrivacyMetricsStore(
        f"sqlite+pysqlite:///{tmp_path / 'aggregate-metrics.db'}"
    )

    store.record_marketing(
        "landing_page_visit",
        source="whatsapp",
        page="year3_maths",
    )
    store.record_marketing(
        "parent_account_created",
        source="whatsapp",
        page="register",
    )
    store.record_voice("tts_used", year_group=3, subject="Maths")

    summary = store.marketing_summary(30)
    voice = store.voice_summary(30)
    assert summary["aggregate_only"] is True
    assert summary["totals"] == {
        "landing_page_visit": 1,
        "parent_account_created": 1,
    }
    assert voice["aggregate_only"] is True
    assert voice["total_events"] == 1
    assert voice["by_age"] == {7: 1}
    assert voice["by_subject"] == {"Maths": 1}

    column_names = {
        column.name
        for table in (store.marketing, store.voice)
        for column in table.columns
    }
    forbidden = {
        "account_id",
        "student_id",
        "learner_id",
        "email",
        "ip",
        "cookie",
        "answer",
        "score",
        "school",
        "free_text",
    }
    assert column_names.isdisjoint(forbidden)


def test_voice_measurement_no_longer_sends_learner_ids_to_rag() -> None:
    app_script = (ROOT / "static" / "js" / "app.js").read_text(encoding="utf-8")
    rag_source = (ROOT / "src" / "homework_rag.py").read_text(encoding="utf-8")
    endpoint_source = (ROOT / "web_app.py").read_text(encoding="utf-8")

    voice_payload = app_script.split("fetch('/api/log-voice-usage'", 1)[1].split(
        "}).catch", 1
    )[0]
    assert "student_id" not in voice_payload
    assert "Voice event:" not in rag_source
    assert "is_voice_event" not in rag_source
    assert "record_voice_event" in endpoint_source


def test_beta_access_is_free_parent_only_and_non_renewing(client) -> None:
    page = client.get("/beta")
    unauthenticated = client.post(
        "/api/billing/beta/redeem",
        json={"invite_code": "not-a-real-code"},
    )

    assert page.status_code == 200
    assert "No payment card, charge or automatic renewal" in page.text
    assert unauthenticated.status_code == 401


def test_beta_access_is_capped_at_fifteen_families(
    tmp_path,
    monkeypatch,
) -> None:
    old_engine = account_store._ENGINE
    old_engine_url = account_store._ENGINE_URL
    old_initialised_path = account_store._INITIALISED_PATH
    database_url = f"sqlite+pysqlite:///{tmp_path / 'beta-access.db'}"
    monkeypatch.setenv("ACCOUNT_DATABASE_URL", database_url)
    monkeypatch.setenv("BETA_ACCESS_ENABLED", "true")
    monkeypatch.setenv("BETA_ACCESS_CODE", "unit-test-parent-beta-code-2026")
    monkeypatch.setenv("BETA_ACCESS_MAX_FAMILIES", "15")
    monkeypatch.setenv("BETA_ACCESS_DURATION_DAYS", "14")
    account_store._ENGINE = None
    account_store._ENGINE_URL = None

    try:
        first_email = "beta-parent-00@example.com"
        first_account = account_store.ensure_account(first_email)
        with pytest.raises(PermissionError):
            account_store.redeem_beta_access(
                first_account["id"],
                "wrong-parent-beta-code",
            )

        first = account_store.redeem_beta_access(
            first_account["id"],
            "unit-test-parent-beta-code-2026",
        )
        repeated = account_store.redeem_beta_access(
            first_account["id"],
            "unit-test-parent-beta-code-2026",
        )
        assert first["subscription"]["plan"] == account_store.BETA_PLAN
        assert first["subscription"]["cancel_at_period_end"] == 1
        assert repeated["already_redeemed"] is True
        assert account_store.account_has_active_subscription(
            first_email,
            ["homework_monthly"],
        )
        assert not account_store.account_has_active_subscription(
            first_email,
            ["elevenplus_monthly"],
        )
        assert not account_store.account_has_active_reward_subscription(
            first_account["id"]
        )

        for index in range(1, 15):
            account = account_store.ensure_account(
                f"beta-parent-{index:02d}@example.com"
            )
            account_store.redeem_beta_access(
                account["id"],
                "unit-test-parent-beta-code-2026",
            )

        sixteenth = account_store.ensure_account(
            "beta-parent-15@example.com"
        )
        with pytest.raises(ValueError, match="cohort is now full"):
            account_store.redeem_beta_access(
                sixteenth["id"],
                "unit-test-parent-beta-code-2026",
            )
    finally:
        account_store._ENGINE = old_engine
        account_store._ENGINE_URL = old_engine_url
        account_store._INITIALISED_PATH = old_initialised_path


def test_beta_feedback_is_five_questions_and_rejects_child_details() -> None:
    page = (ROOT / "static" / "beta-feedback.html").read_text(encoding="utf-8")
    script = (ROOT / "static" / "js" / "beta-feedback.js").read_text(
        encoding="utf-8"
    )
    message_store = (
        ROOT / "src" / "webapp" / "message_store.py"
    ).read_text(encoding="utf-8")

    assert page.count("1. How easy") == 1
    assert "2. Could the learner" in page
    assert "3. How useful" in page
    assert "4. What was the most confusing" in page
    assert "5. Would your family" in page
    assert "do not include a child’s name, school, birthday" in page
    assert "category: 'beta_feedback'" in script
    assert '"beta_feedback"' in message_store
