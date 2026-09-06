import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.health import router as health_router
from app.routes.auth import router as auth_router
from app.routes.integrations import router as integrations_router
from app.routes.organizations import router as organizations_router
from app.routes.slack import router as slack_router

settings = get_settings()

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
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    supplied_request_id = request.headers.get("X-Request-ID")
    request_id = (
        supplied_request_id
        if supplied_request_id and len(supplied_request_id) <= 128
        else str(uuid.uuid4())
    )
    request.state.request_id = request_id

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    return {"service": "brain-api", "version": "0.1.0"}


app.include_router(health_router)
app.include_router(auth_router, prefix=settings.api_prefix)
app.include_router(organizations_router, prefix=settings.api_prefix)
app.include_router(integrations_router, prefix=settings.api_prefix)
app.include_router(slack_router, prefix=settings.api_prefix)
