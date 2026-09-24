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
from app.observability import (
    JSONLogFormatter,
    log_event,
    metrics_response,
    record_ai_request,
    record_connector_event,
    record_connector_sync,
)


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
    return Request(
        {
            "type": "http",
            "headers": headers,
            "method": "GET",
            "path": "/metrics",
        }
    )


def test_json_logging_redacts_credentials_and_bearer_tokens() -> None:
    record = logging.LogRecord(
        name="brain.test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg=(
            'api_key=super-secret "access_token":"json-secret" '
            "Authorization: Bearer bearer-secret sk-abcdefghijklmnop "
            "ghp_abcdefghijklmnopqrstuvwxyz123456 "
            "xoxb-123456789012-abcdefghijklmnop"
        ),
        args=(),
        exc_info=None,
    )

    payload = json.loads(JSONLogFormatter().format(record))

    assert payload["level"] == "ERROR"
    for secret in (
        "super-secret",
        "json-secret",
        "bearer-secret",
        "sk-abcdefghijklmnop",
        "ghp_abcdefghijklmnopqrstuvwxyz123456",
        "xoxb-123456789012-abcdefghijklmnop",
    ):
        assert secret not in payload["message"]
    assert "[REDACTED]" in payload["message"]


def test_json_logging_keeps_safe_background_context_and_drops_unknown_extra() -> None:
    organization_id = str(uuid.uuid4())
    record = logging.LogRecord(
        name="brain.connector",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="connector.sync.succeeded",
        args=(),
        exc_info=None,
    )
    record.organization_id = organization_id
    record.integration_id = str(uuid.uuid4())
    record.secret_payload = "must-not-be-emitted"

    payload = json.loads(JSONLogFormatter().format(record))

    assert payload["organization_id"] == organization_id
    assert "integration_id" in payload
    assert "secret_payload" not in payload
    assert "must-not-be-emitted" not in json.dumps(payload)


def test_structured_event_fields_cannot_overwrite_log_record_attributes() -> None:
    logger = logging.getLogger("brain.test.reserved-fields")
    records: list[logging.LogRecord] = []

    class Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = Capture()
    logger.addHandler(handler)
    logger.propagate = False
    try:
        log_event(
            logger,
            logging.INFO,
            "connector.event.persisted",
            created=True,
            event_created=True,
        )
    finally:
        logger.removeHandler(handler)
        logger.propagate = True

    assert len(records) == 1
    assert records[0].event_created is True
    assert isinstance(records[0].created, float)


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


def test_metrics_can_be_disabled() -> None:
    settings = Settings(_env_file=None, metrics_enabled=False)

    with pytest.raises(HTTPException) as disabled:
        metrics_response(_request(), settings)

    assert disabled.value.status_code == 404


def test_ai_and_connector_metrics_drop_tenant_configurable_dimensions() -> None:
    provider = "observability-test-provider"
    model = "observability-test-model"
    connector = "observability-test-connector"
    record_ai_request(
        provider=provider,
        model=model,
        status_value="succeeded",
        latency_ms=125,
        cost_nano_usd=42,
    )
    record_connector_event(provider=connector, created=True)
    record_connector_sync(provider=connector, succeeded=False)
    response = metrics_response(
        _request(),
        Settings(_env_file=None, metrics_enabled=True),
    )
    body = bytes(response.body)

    assert b"brain_ai_requests_total" in body
    assert b"brain_ai_request_duration_seconds" in body
    assert b"brain_ai_cost_nano_usd_total" in body
    assert b"brain_connector_events_total" in body
    assert b"brain_connector_sync_total" in body
    assert provider.encode() not in body
    assert model.encode() not in body
    assert connector.encode() not in body


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


def test_cors_exposes_request_id_to_frontend(client) -> None:
    response = client.get(
        "/",
        headers={"Origin": "http://localhost:3000"},
    )

    assert response.status_code == 200
    exposed = response.headers.get("access-control-expose-headers", "")
    assert "X-Request-ID" in exposed
