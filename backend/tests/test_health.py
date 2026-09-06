from fastapi.testclient import TestClient

from app import health
from app.main import app

client = TestClient(app)


def test_liveness() -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["x-request-id"]


def test_readiness_when_database_is_available(monkeypatch) -> None:
    monkeypatch.setattr(health, "database_ready", lambda: True)
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "up"}


def test_readiness_when_database_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(health, "database_ready", lambda: False)
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "database": "down"}
