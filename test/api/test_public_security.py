from __future__ import annotations

import pytest

pytestmark = pytest.mark.api


def test_health_and_public_pages(client) -> None:
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    for path in ("/", "/app", "/elevenplus-practice", "/elevenplus-year-round-plan"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert "text/html" in response.headers.get("content-type", "")


def test_security_headers_are_present(client) -> None:
    response = client.get("/")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["cross-origin-resource-policy"] == "same-origin"


def test_client_id_never_exposes_or_derives_response_from_ip(client) -> None:
    response = client.get(
        "/api/client-id",
        headers={"x-forwarded-for": "203.0.113.42"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "ip" not in body
    assert body["client_id"].startswith("anon_")
    assert "203.0.113.42" not in response.text


def test_cross_site_browser_write_is_blocked(client) -> None:
    response = client.post(
        "/api/logout",
        headers={"Origin": "https://evil.example"},
    )
    assert response.status_code == 403


def test_sensitive_responses_are_not_cached(client) -> None:
    response = client.get("/api/check-subscription")
    assert response.status_code == 200
    assert "no-store" in response.headers.get("cache-control", "")
