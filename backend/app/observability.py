import hmac
import json
import logging
import re
import time
import uuid
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from fastapi import HTTPException, Request, Response, status
from opentelemetry import propagate, trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import SpanKind, Status, StatusCode
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

from app.config import Settings

_request_id: ContextVar[str | None] = ContextVar("brain_request_id", default=None)
_organization_id: ContextVar[str | None] = ContextVar("brain_organization_id", default=None)

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_SENSITIVE_TEXT_PATTERNS = (
    re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+"),
    re.compile(
        r"(?i)((?:api[_-]?key|access[_-]?token|refresh[_-]?token|secret)"
        r"\s*[:=]\s*)[^\s,;]+"
    ),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
)
_SAFE_FIELDS = frozenset(
    {
        "request_id",
        "ai_request_id",
        "provider_request_id",
        "trace_id",
        "span_id",
        "organization_id",
        "integration_id",
        "provider",
        "model",
        "route",
        "http_method",
        "status_code",
        "duration_ms",
        "error_code",
        "cost_nano_usd",
        "source_event_type",
        "delivery_kind",
        "created",
        "dependency",
        "dependency_status",
        "worker",
        "processed",
        "remaining",
    }
)

HTTP_REQUESTS = Counter(
    "brain_http_requests_total",
    "HTTP requests handled by Brain",
    ("method", "route", "status_class"),
)
HTTP_LATENCY = Histogram(
    "brain_http_request_duration_seconds",
    "Brain HTTP request duration",
    ("method", "route"),
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 1.5, 2.5, 5, 10, 30),
)
DEPENDENCY_READY = Gauge(
    "brain_dependency_ready",
    "Whether a readiness dependency is currently available",
    ("dependency",),
)
DEPENDENCY_LATENCY = Histogram(
    "brain_dependency_check_duration_seconds",
    "Readiness dependency check duration",
    ("dependency",),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)
AI_REQUESTS = Counter(
    "brain_ai_requests_total",
    "Governed AI provider requests",
    ("provider", "model", "status"),
)
AI_LATENCY = Histogram(
    "brain_ai_request_duration_seconds",
    "Governed AI provider request duration",
    ("provider", "model"),
    buckets=(0.1, 0.25, 0.5, 1, 2.5, 5, 10, 20, 30, 60, 120),
)
AI_COST_NANO_USD = Counter(
    "brain_ai_cost_nano_usd_total",
    "Resolved governed AI cost in nano-USD",
    ("provider", "model"),
)
CONNECTOR_EVENTS = Counter(
    "brain_connector_events_total",
    "Raw connector event persistence attempts",
    ("provider", "result"),
)
CONNECTOR_SYNCS = Counter(
    "brain_connector_sync_total",
    "Connector sync lifecycle outcomes",
    ("provider", "status"),
)

_tracing_initialized = False


def _redact_text(value: str) -> str:
    redacted = value
    for pattern in _SENSITIVE_TEXT_PATTERNS:
        redacted = pattern.sub(
            lambda match: (
                f"{match.group(1)}[REDACTED]" if match.lastindex else "[REDACTED]"
            ),
            redacted,
        )
    return redacted


def _trace_fields() -> dict[str, str | None]:
    span = trace.get_current_span()
    context = span.get_span_context()
    if not context.is_valid:
        return {"trace_id": None, "span_id": None}
    return {
        "trace_id": format(context.trace_id, "032x"),
        "span_id": format(context.span_id, "016x"),
    }


class JSONLogFormatter(logging.Formatter):
    converter = time.gmtime

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname,
            "logger": record.name,
            "message": _redact_text(record.getMessage()),
            "request_id": _request_id.get(),
            "organization_id": _organization_id.get(),
            **_trace_fields(),
        }
        for field in _SAFE_FIELDS:
            if field in payload:
                continue
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = (
                    _redact_text(str(value)) if isinstance(value, str) else value
                )
        if record.exc_info:
            payload["exception_type"] = record.exc_info[0].__name__
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def configure_logging(settings: Settings) -> None:
    root = logging.getLogger()
    root.setLevel(settings.log_level.upper())
    handler = logging.StreamHandler()
    handler.setFormatter(JSONLogFormatter())
    root.handlers.clear()
    root.addHandler(handler)


def configure_tracing(settings: Settings) -> None:
    global _tracing_initialized
    if _tracing_initialized:
        return
    provider = TracerProvider(
        resource=Resource.create({SERVICE_NAME: settings.otel_service_name})
    )
    if settings.otel_exporter_otlp_endpoint:
        exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _tracing_initialized = True


def get_tracer(name: str):
    return trace.get_tracer(name)


def bind_organization_context(organization_id: uuid.UUID | str) -> None:
    _organization_id.set(str(organization_id))


def log_event(logger: logging.Logger, level: int, event: str, **fields: Any) -> None:
    safe = {key: value for key, value in fields.items() if key in _SAFE_FIELDS}
    logger.log(level, event, extra=safe)


def record_dependency_check(
    dependency: str,
    *,
    ready: bool,
    duration_seconds: float,
) -> None:
    DEPENDENCY_READY.labels(dependency=dependency).set(1 if ready else 0)
    DEPENDENCY_LATENCY.labels(dependency=dependency).observe(
        max(0.0, duration_seconds)
    )


def record_ai_request(
    *,
    provider: str,
    model: str,
    status_value: str,
    latency_ms: int,
    cost_nano_usd: int | None = None,
) -> None:
    AI_REQUESTS.labels(provider=provider, model=model, status=status_value).inc()
    AI_LATENCY.labels(provider=provider, model=model).observe(max(0, latency_ms) / 1000)
    if cost_nano_usd is not None and cost_nano_usd >= 0:
        AI_COST_NANO_USD.labels(provider=provider, model=model).inc(cost_nano_usd)


def record_connector_event(*, provider: str, created: bool) -> None:
    result = "created" if created else "duplicate"
    CONNECTOR_EVENTS.labels(provider=provider, result=result).inc()


def record_connector_sync(*, provider: str, succeeded: bool) -> None:
    result = "succeeded" if succeeded else "failed"
    CONNECTOR_SYNCS.labels(provider=provider, status=result).inc()


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    return path if isinstance(path, str) and path else "__unmatched__"


def _request_id_from_header(value: str | None) -> str:
    if value and _REQUEST_ID_RE.fullmatch(value):
        return value
    return str(uuid.uuid4())


async def observe_http_request(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    request_id = _request_id_from_header(request.headers.get("X-Request-ID"))
    request.state.request_id = request_id
    request_token = _request_id.set(request_id)
    organization_token = _organization_id.set(None)
    started = time.perf_counter()
    parent_context = propagate.extract(dict(request.headers))
    tracer = get_tracer("brain.http")
    response: Response | None = None
    status_code = 500
    try:
        with tracer.start_as_current_span(
            "http.request",
            context=parent_context,
            kind=SpanKind.SERVER,
        ) as span:
            span.set_attribute("http.request.method", request.method)
            try:
                response = await call_next(request)
                status_code = response.status_code
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR))
                raise
            finally:
                duration = max(0.0, time.perf_counter() - started)
                route = _route_template(request)
                status_class = f"{status_code // 100}xx"
                HTTP_REQUESTS.labels(
                    method=request.method,
                    route=route,
                    status_class=status_class,
                ).inc()
                HTTP_LATENCY.labels(method=request.method, route=route).observe(duration)
                span.set_attribute("http.route", route)
                span.set_attribute("http.response.status_code", status_code)
                span.set_attribute("brain.request_id", request_id)
                if status_code >= 500:
                    span.set_status(Status(StatusCode.ERROR))
                organization_id = _organization_id.get()
                if organization_id:
                    span.set_attribute("brain.organization_id", organization_id)
                log_event(
                    logging.getLogger("brain.http"),
                    logging.ERROR if status_code >= 500 else logging.INFO,
                    "http.request.completed",
                    request_id=request_id,
                    organization_id=organization_id,
                    route=route,
                    http_method=request.method,
                    status_code=status_code,
                    duration_ms=round(duration * 1000),
                )
        assert response is not None
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response
    finally:
        _organization_id.reset(organization_token)
        _request_id.reset(request_token)


def metrics_response(request: Request, settings: Settings) -> Response:
    if not settings.metrics_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if settings.metrics_bearer_token:
        supplied = request.headers.get("Authorization", "")
        expected = f"Bearer {settings.metrics_bearer_token}"
        if not hmac.compare_digest(supplied, expected):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized",
            )
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@dataclass(frozen=True, slots=True)
class DependencyCheck:
    name: str
    ready: bool
    latency_ms: int
