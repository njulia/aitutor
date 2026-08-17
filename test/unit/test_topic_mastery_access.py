from pathlib import Path

from test.conftest import register_or_login


def test_topic_mastery_access_endpoint_uses_server_entitlement_for_premium(
    client, unique_email, monkeypatch
):
    register_or_login(client, unique_email)
    import web_app

    monkeypatch.setattr(web_app, "user_has_subscription", lambda *args, **kwargs: True)
    response = client.get("/api/elevenplus/topic-mastery/access")
    assert response.status_code == 200, response.text
    assert response.json() == {"success": True, "has_access": True}


def test_topic_mastery_access_endpoint_denies_without_entitlement(
    client, unique_email, monkeypatch
):
    register_or_login(client, unique_email)
    import web_app

    monkeypatch.setattr(web_app, "user_has_subscription", lambda *args, **kwargs: False)
    response = client.get("/api/elevenplus/topic-mastery/access")
    assert response.status_code == 200, response.text
    assert response.json() == {"success": True, "has_access": False}


def test_topic_mastery_frontend_uses_server_access_and_mentions_test_users():
    page = Path("static/elevenplus-topic-mastery.html").read_text(encoding="utf-8")
    pricing = Path("static/js/pricing.js").read_text(encoding="utf-8")
    assert "/api/elevenplus/topic-mastery/access" in page
    assert "Test accounts can use Topic Mastery free." in page
    assert "accessData.has_access === true" in page
    assert "/api/elevenplus/topic-mastery/access" in pricing
    assert "data.has_access === true" in pricing


def test_topic_mastery_access_endpoint_allows_test_user(client, unique_email, monkeypatch):
    register_or_login(client, unique_email)
    import web_app

    monkeypatch.setattr(web_app, "is_user_test", lambda username: True)
    monkeypatch.setattr(web_app, "user_has_subscription", lambda *args, **kwargs: True)
    response = client.get("/api/elevenplus/topic-mastery/access")
    assert response.status_code == 200, response.text
    assert response.json() == {"success": True, "has_access": True}
