import json
import logging
import uuid

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.requests import Request

from app import health
from app.config import Settings
from app.observability import JSONLogFormatter, metrics_response


class ReadyConnection:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def execute(self, statement):
        del statement
        return None


class ReadyEngine:
    def connect(self) -> ReadyConnection:
        return ReadyConnection()


class DownEngine:
    def connect(self):
        raise SQLAlchemyError("database unavailable")


def _request(authorization: str | None = None) -> Request:
    headers = []
    if authorization is not None:
        headers.append((b"authorization", authorization.encode()))
    return Request({"type": "http", "headers": headers, "method": "GET", "path": "/metrics"})


def test_json_logging_redacts_credentials_and_bearer_tokens() -> None:
    record = logging.LogRecord(
        name="brain.test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg=(
            "api_key=super-secret Authorization: Bearer bearer-secret "
            "sk-abcdefghijklmnop"
        ),
        args=(),
        exc_info=None,
    )

    payload = json.loads(JSONLogFormatter().format(record))

    assert payload["level"] == "ERROR"
    assert "super-secret" not in payload["message"]
    assert "bearer-secret" not in payload["message"]
    assert "sk-abcdefghijklmnop" not in payload["message"]
    assert "[REDACTED]" in payload["message"]


def test_metrics_require_configured_bearer_token_and_do_not_expose_tenant_labels() -> None:
    settings = Settings(
        _env_file=None,
        metrics_enabled=True,
        metrics_bearer_token="metrics-secret",
    )
    with pytest.raises(HTTPException) as denied:
        metrics_response(_request("Bearer wrong"), settings)
    assert denied.value.status_code == 401

    response = metrics_response(_request("Bearer metrics-secret"), settings)
    body = bytes(response.body)
    assert b"brain_http_requests_total" in body
    assert b"organization_id=" not in body
    assert b"user_id=" not in body


def test_production_requires_metrics_token_when_metrics_are_enabled() -> None:
    with pytest.raises(ValidationError, match="BRAIN_METRICS_BEARER_TOKEN"):
        Settings(
            _env_file=None,
            environment="production",
            app_secret="production-secret",
            workos_client_id="client_123",
            metrics_enabled=True,
            metrics_bearer_token=None,
        )


def test_production_otlp_export_requires_https() -> None:
    with pytest.raises(ValidationError, match="Production OTLP export must use HTTPS"):
        Settings(
            _env_file=None,
            environment="production",
            app_secret="production-secret",
            workos_client_id="client_123",
            metrics_enabled=False,
            otel_exporter_otlp_endpoint="http://collector.internal/v1/traces",
        )


def test_liveness_does_not_depend_on_database(monkeypatch) -> None:
    monkeypatch.setattr(health, "get_engine", lambda: DownEngine())

    assert health.live() == {"status": "ok"}


def test_readiness_reports_dependency_latency_and_failure(monkeypatch) -> None:
    monkeypatch.setattr(health, "get_engine", lambda: ReadyEngine())
    up = health.ready()
    assert up.status_code == 200
    up_payload = json.loads(bytes(up.body))
    assert up_payload["status"] == "ready"
    assert up_payload["dependencies"]["database"]["status"] == "up"
    assert up_payload["dependencies"]["database"]["latency_ms"] >= 0

    monkeypatch.setattr(health, "get_engine", lambda: DownEngine())
    down = health.ready()
    assert down.status_code == 503
    down_payload = json.loads(bytes(down.body))
    assert down_payload["status"] == "not_ready"
    assert down_payload["dependencies"]["database"]["status"] == "down"


def test_http_request_id_is_preserved_only_when_safe(client) -> None:
    accepted = client.get("/", headers={"X-Request-ID": "req-123.safe"})
    assert accepted.status_code == 200
    assert accepted.headers["X-Request-ID"] == "req-123.safe"

    unsafe_value = "request/with/high-cardinality/path"
    replaced = client.get("/", headers={"X-Request-ID": unsafe_value})
    assert replaced.status_code == 200
    assert replaced.headers["X-Request-ID"] != unsafe_value
    uuid.UUID(replaced.headers["X-Request-ID"])
