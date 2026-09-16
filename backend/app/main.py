from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.health import router as health_router
from app.observability import (
    configure_logging,
    configure_tracing,
    metrics_response,
    observe_http_request,
)
from app.routes.admin_center import router as admin_center_router
from app.routes.agent_workspace import router as agent_workspace_router
from app.routes.agent_workspace_actions import router as agent_workspace_actions_router
from app.routes.agents import router as agents_router
from app.routes.ai_gateway import router as ai_gateway_router
from app.routes.ai_usage import router as ai_usage_router
from app.routes.api_registry import router as api_registry_router
from app.routes.api_registry_usage import router as api_registry_usage_router
from app.routes.ask_brain import router as ask_brain_router
from app.routes.auth import router as auth_router
from app.routes.data_governance import router as data_governance_router
from app.routes.decision_memory import router as decision_memory_router
from app.routes.direct_messages import router as direct_messages_router
from app.routes.evidence import router as evidence_router
from app.routes.executive_overview import router as executive_overview_router
from app.routes.github import router as github_router
from app.routes.identities import router as identities_router
from app.routes.integrations import router as integrations_router
from app.routes.native_chat import router as native_chat_router
from app.routes.native_conversation import router as native_conversation_router
from app.routes.organizations import router as organizations_router
from app.routes.project_status import router as project_status_router
from app.routes.runtime_discovery import router as runtime_discovery_router
from app.routes.search import router as search_router
from app.routes.slack import router as slack_router
from app.routes.work_graph import router as work_graph_router
from app.routes.workspace_navigation import router as workspace_navigation_router

settings = get_settings()
configure_logging(settings)
configure_tracing(settings)

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url=None if settings.environment.lower() == "production" else "/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Request-ID",
        "Idempotency-Key",
        "baggage",
        "traceparent",
        "tracestate",
    ],
    expose_headers=["X-Request-ID"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    return await observe_http_request(request, call_next)


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    return {"service": "brain-api", "version": "0.1.0"}


@app.get("/metrics", include_in_schema=False)
def metrics(request: Request):
    return metrics_response(request, settings)


app.include_router(health_router)
app.include_router(auth_router, prefix=settings.api_prefix)
app.include_router(runtime_discovery_router, prefix=settings.api_prefix)
app.include_router(organizations_router, prefix=settings.api_prefix)
app.include_router(integrations_router, prefix=settings.api_prefix)
app.include_router(evidence_router, prefix=settings.api_prefix)
app.include_router(native_chat_router, prefix=settings.api_prefix)
app.include_router(native_conversation_router, prefix=settings.api_prefix)
app.include_router(direct_messages_router, prefix=settings.api_prefix)
app.include_router(slack_router, prefix=settings.api_prefix)
app.include_router(github_router, prefix=settings.api_prefix)
app.include_router(identities_router, prefix=settings.api_prefix)
app.include_router(work_graph_router, prefix=settings.api_prefix)
app.include_router(workspace_navigation_router, prefix=settings.api_prefix)
app.include_router(search_router, prefix=settings.api_prefix)
app.include_router(decision_memory_router, prefix=settings.api_prefix)
app.include_router(project_status_router, prefix=settings.api_prefix)
app.include_router(executive_overview_router, prefix=settings.api_prefix)
app.include_router(ai_gateway_router, prefix=settings.api_prefix)
app.include_router(ask_brain_router, prefix=settings.api_prefix)
app.include_router(ai_usage_router, prefix=settings.api_prefix)
app.include_router(api_registry_router, prefix=settings.api_prefix)
app.include_router(api_registry_usage_router, prefix=settings.api_prefix)
app.include_router(data_governance_router, prefix=settings.api_prefix)
app.include_router(agents_router, prefix=settings.api_prefix)
app.include_router(agent_workspace_router, prefix=settings.api_prefix)
app.include_router(agent_workspace_actions_router, prefix=settings.api_prefix)
app.include_router(admin_center_router, prefix=settings.api_prefix)
