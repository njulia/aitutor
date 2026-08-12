from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.webapp.school_finder_routes import (
    _is_secondary_school,
    _normalise_postcode,
    build_school_finder_router,
)


def test_invalid_postcode_rejected():
    app = FastAPI()
    app.include_router(build_school_finder_router())
    client = TestClient(app)
    response = client.post(
        "/api/schools/nearby",
        json={"postcode": "ZZZZ 9ZZ"},
    )
    assert response.status_code == 400


def test_secondary_classifier_accepts_sparse_secondary_academy():
    assert _is_secondary_school({"name": "Chobham Academy"}) is True


def test_secondary_classifier_accepts_common_secondary_names():
    assert _is_secondary_school({"name": "Example Grammar School"}) is True
    assert _is_secondary_school({"name": "Example Secondary School"}) is True
    assert _is_secondary_school({"name": "Example High School"}) is True
    assert _is_secondary_school({"name": "Example Upper School"}) is True


def test_secondary_classifier_accepts_explicit_phase():
    assert _is_secondary_school(
        {"name": "Example School", "school:level": "secondary"}
    ) is True


def test_primary_school_is_not_secondary_even_if_academy():
    assert _is_secondary_school(
        {"name": "Example Primary Academy", "school:level": "primary"}
    ) is False


def test_nearby_endpoint_passes_child_context_without_storage():
    app = FastAPI()
    app.include_router(build_school_finder_router())
    payload = {
        "postcode": "N22 8AA",
        "area": "Test",
        "schools": [],
    }
    with patch(
        "src.webapp.school_finder_routes._fetch_nearby",
        new=AsyncMock(return_value=payload),
    ) as mocked:
        client = TestClient(app)
        response = client.post(
            "/api/schools/nearby",
            json={
                "postcode": "N22 8AA",
                "entry_year": "Year 7",
                "child_gender": "girl",
            },
        )
        assert response.status_code == 200
        mocked.assert_awaited_once_with("N22 8AA", "Year 7", "girl")


def test_overpass_uses_get_and_accepts_empty_result():
    import httpx
    import pytest
    from src.webapp.school_finder_routes import _fetch_overpass_elements

    class FakeClient:
        def __init__(self):
            self.calls = []

        async def get(self, endpoint, **kwargs):
            self.calls.append((endpoint, kwargs))
            return httpx.Response(200, json={"elements": []}, request=httpx.Request("GET", endpoint))

    async def run():
        client = FakeClient()
        result = await _fetch_overpass_elements(client, 51.6, -0.11)
        assert result == []
        assert client.calls
        assert all("data" in call[1]["params"] for call in client.calls)

    import asyncio
    asyncio.run(run())


def test_overpass_falls_back_to_next_mirror_after_failure():
    import httpx
    from src.webapp.school_finder_routes import _fetch_overpass_elements

    class FakeClient:
        def __init__(self):
            self.calls = []

        async def get(self, endpoint, **kwargs):
            self.calls.append(endpoint)
            if len(self.calls) == 1:
                raise httpx.ConnectError("blocked", request=httpx.Request("GET", endpoint))
            return httpx.Response(
                200,
                json={"elements": [{"type": "node", "id": 1, "lat": 51.6, "lon": -0.11, "tags": {"name": "Example Academy"}}]},
                request=httpx.Request("GET", endpoint),
            )

    import asyncio
    async def run():
        client = FakeClient()
        result = await _fetch_overpass_elements(client, 51.6, -0.11)
        assert result[0]["id"] == 1
        assert len(client.calls) == 2

    asyncio.run(run())
