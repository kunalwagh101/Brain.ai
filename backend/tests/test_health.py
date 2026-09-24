from fastapi.testclient import TestClient

from app import health
from app.main import app
from app.observability import DependencyCheck

client = TestClient(app)


def test_liveness() -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["x-request-id"]


def test_readiness_when_database_is_available(monkeypatch) -> None:
    monkeypatch.setattr(
        health,
        "database_readiness",
        lambda: DependencyCheck(name="database", ready=True, latency_ms=7),
    )
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "dependencies": {"database": {"status": "up", "latency_ms": 7}},
    }


def test_readiness_when_database_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(
        health,
        "database_readiness",
        lambda: DependencyCheck(name="database", ready=False, latency_ms=11),
    )
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "dependencies": {"database": {"status": "down", "latency_ms": 11}},
    }
