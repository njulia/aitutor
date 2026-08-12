from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.webapp.school_finder_routes import build_school_finder_admin_router


def test_admin_can_exclude_and_restore_school(tmp_path, monkeypatch):
    monkeypatch.setenv("ACCOUNT_DB_PATH", str(tmp_path / "accounts.db"))
    import src.webapp.school_finder_exclusions as exclusions
    exclusions._ENGINE = None
    exclusions._ENGINE_URL = None

    app = FastAPI()
    app.include_router(build_school_finder_admin_router(lambda req: "admin@example.com"))
    client = TestClient(app)

    response = client.post("/api/admin/schools/exclude", json={
        "source_id": "osm:way:123",
        "name": "Example Academy",
        "latitude": 51.5,
        "longitude": -0.1,
        "reason": "Primary school",
    })
    assert response.status_code == 200

    response = client.get("/api/admin/schools/excluded")
    assert response.status_code == 200
    assert response.json()["schools"][0]["name"] == "Example Academy"

    assert exclusions.is_school_excluded(
        source_id="osm:way:123",
        name="Example Academy",
        latitude=51.5,
        longitude=-0.1,
    )

    response = client.delete("/api/admin/schools/exclude/osm:way:123")
    assert response.status_code == 200
    assert not exclusions.is_school_excluded(
        source_id="osm:way:123",
        name="Example Academy",
        latitude=51.5,
        longitude=-0.1,
    )
