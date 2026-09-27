import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import Settings, get_settings


def _enable(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "environment", "staging")
    monkeypatch.setattr(settings, "demo_signup_enabled", True)
    monkeypatch.setattr(settings, "app_secret", "test-staging-secret-with-at-least-32-characters")


def test_demo_signup_uses_real_workspace_routes_and_revokes_on_signout(
    client: TestClient, monkeypatch
) -> None:
    _enable(monkeypatch)
    signup = client.post("/api/v1/demo-sessions", json={"name": "Kunal"})
    assert signup.status_code == 201
    assert signup.headers["cache-control"] == "no-store"
    token = signup.json()["access_token"]
    assert signup.json()["expires_at"]
    headers = {"Authorization": f"Bearer {token}"}

    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["display_name"] == "Kunal"

    orgs = client.get("/api/v1/organizations", headers=headers)
    assert orgs.status_code == 200
    assert len(orgs.json()) == 1
    org_id = orgs.json()[0]["id"]
    channel = client.post(
        f"/api/v1/organizations/{org_id}/native-channels",
        json={"name": "Testing"},
        headers=headers,
    )
    assert channel.status_code == 201
    channel_id = channel.json()["id"]
    message = client.post(
        f"/api/v1/organizations/{org_id}/native-channels/{channel_id}/messages",
        json={"body": "Real backend message"},
        headers=headers,
    )
    assert message.status_code == 201
    history = client.get(
        f"/api/v1/organizations/{org_id}/native-channels/{channel_id}/messages",
        headers=headers,
    )
    assert [item["body"] for item in history.json()] == ["Real backend message"]
    assert client.delete("/api/v1/demo-sessions/current", headers=headers).status_code == 204
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_demo_disabled_in_production_and_rate_limited(client: TestClient, monkeypatch) -> None:
    with pytest.raises(ValueError, match="Demo signup cannot be enabled in production"):
        Settings(
            environment="production",
            demo_signup_enabled=True,
            app_secret="some-strong-staging-only-secret-long-enough",
        )
    settings = get_settings()
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "demo_signup_enabled", True)
    assert client.post("/api/v1/demo-sessions", json={"name": "A"}).status_code == 404

    _enable(monkeypatch)
    for number in range(5):
        assert (
            client.post("/api/v1/demo-sessions", json={"name": f"Tester {number}"}).status_code
            == 201
        )
    assert client.post("/api/v1/demo-sessions", json={"name": "Extra"}).status_code == 429


def test_demo_expiry_and_org_isolation(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    _enable(monkeypatch)
    first = client.post("/api/v1/demo-sessions", json={"name": "One"}).json()
    second = client.post("/api/v1/demo-sessions", json={"name": "Two"}).json()
    first_headers = {"Authorization": f"Bearer {first['access_token']}"}
    second_headers = {"Authorization": f"Bearer {second['access_token']}"}
    first_org = client.get("/api/v1/organizations", headers=first_headers).json()[0]["id"]
    assert client.get(f"/api/v1/organizations/{first_org}", headers=second_headers).status_code in {
        403,
        404,
    }

    from sqlalchemy import select

    from app.demo_session_models import DemoSession

    session = db_session.scalar(
        select(DemoSession).where(DemoSession.user_id == uuid.UUID(first["user_id"]))
    )
    session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    db_session.commit()
    assert client.get("/api/v1/auth/me", headers=first_headers).status_code == 401
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": "Bearer brdemo_fake"}).status_code
        == 401
    )
