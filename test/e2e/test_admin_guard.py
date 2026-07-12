from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from src.webapp.runtime import AdminPathGuardMiddleware


def test_legacy_admin_routes_are_guarded():
    app = FastAPI()

    def require_admin(request: Request):
        if request.headers.get("X-Test-Admin") != "yes":
            raise HTTPException(status_code=403, detail="Admin access denied")

    app.add_middleware(AdminPathGuardMiddleware, require_admin=require_admin)

    @app.get("/api/admin/legacy")
    async def legacy():
        return {"secret": True}

    @app.get("/api/public")
    async def public():
        return {"ok": True}

    client = TestClient(app)
    assert client.get("/api/admin/legacy").status_code == 403
    assert client.get("/api/admin/legacy", headers={"X-Test-Admin": "yes"}).status_code == 200
    assert client.get("/api/public").status_code == 200
