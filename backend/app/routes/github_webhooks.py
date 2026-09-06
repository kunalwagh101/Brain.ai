import json
import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.canonical_events import canonicalize_raw_event
from app.config import Settings, get_settings
from app.database import get_db
from app.github import (
    GitHubConfigurationError,
    load_github_credentials,
    verify_github_webhook,
)
from app.integrations import connection_can_sync
from app.raw_events import MAX_RAW_EVENT_BYTES, RawEventRejectedError, persist_raw_event
from app.routes.github_common import active_github_installations
from app.secrets import SecretStore, get_secret_store

router = APIRouter(tags=["github"])
logger = logging.getLogger("brain.github")

_SUPPORTED_EVENTS = {
    "push",
    "pull_request",
    "issues",
    "deployment",
    "deployment_status",
    "workflow_run",
    "repository",
}


def _source_timestamp(event_name: str, payload: dict[str, object]) -> datetime | None:
    candidates: list[object] = []
    if event_name == "push":
        head_commit = payload.get("head_commit")
        if isinstance(head_commit, dict):
            candidates.append(head_commit.get("timestamp"))
    object_names = {
        "pull_request": "pull_request",
        "issues": "issue",
        "deployment": "deployment",
        "deployment_status": "deployment_status",
        "workflow_run": "workflow_run",
        "repository": "repository",
    }
    object_name = object_names.get(event_name)
    if object_name:
        obj = payload.get(object_name)
        if isinstance(obj, dict):
            candidates.extend((obj.get("updated_at"), obj.get("created_at")))

    for value in candidates:
        if not isinstance(value, str) or not value:
            continue
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            continue
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return None


def _repository_permissions(payload: dict[str, object]) -> tuple[str, list[str]]:
    repository = payload.get("repository")
    if not isinstance(repository, dict):
        return "installation", []
    repository_id = repository.get("id")
    visibility = repository.get("visibility")
    private = repository.get("private") is True
    normalized_visibility = visibility if isinstance(visibility, str) else None
    if normalized_visibility == "public" or (normalized_visibility is None and not private):
        return "public_repository", []
    if isinstance(repository_id, int):
        prefix = normalized_visibility or "private"
        return f"{prefix}_repository", [f"github:repository:{repository_id}"]
    return "restricted_repository", []


@router.post("/webhooks/github/events")
async def github_events(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[Session, Depends(get_db)],
    secret_store: Annotated[SecretStore, Depends(get_secret_store)],
) -> dict[str, object]:
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_RAW_EVENT_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Payload too large",
                )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Content-Length",
            ) from None

    raw_body = await request.body()
    if len(raw_body) > MAX_RAW_EVENT_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Payload too large",
        )

    try:
        credentials = load_github_credentials(settings, secret_store)
    except GitHubConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub webhook is not configured",
        ) from exc

    signature = request.headers.get("x-hub-signature-256", "")
    if not verify_github_webhook(
        raw_body,
        signature=signature,
        secret=credentials.webhook_secret,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid GitHub signature",
        )

    delivery_id = request.headers.get("x-github-delivery", "")
    event_name = request.headers.get("x-github-event", "")
    if not delivery_id or len(delivery_id) > 255 or not event_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub webhook headers are incomplete",
        )
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid GitHub JSON",
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid GitHub event",
        )
    if event_name == "ping":
        return {"ok": True, "zen": payload.get("zen")}
    if event_name not in _SUPPORTED_EVENTS:
        return {"ok": True, "ignored": "unsupported_event"}

    installation = payload.get("installation")
    installation_id = installation.get("id") if isinstance(installation, dict) else None
    if not isinstance(installation_id, int):
        return {"ok": True, "ignored": "installation_missing"}

    connections = [
        item
        for item in active_github_installations(db, installation_id)
        if connection_can_sync(item)
    ]
    if not connections:
        return {"ok": True, "ignored": "installation_not_connected"}
    if len(connections) != 1:
        logger.error(
            "GitHub installation has multiple active Brain connections",
            extra={"installation_id": installation_id},
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub installation connection is ambiguous",
        )
    connection = connections[0]
    visibility, source_acl = _repository_permissions(payload)

    try:
        persisted = persist_raw_event(
            db,
            organization_id=connection.organization_id,
            integration_connection_id=connection.id,
            provider="github",
            source_event_id=delivery_id,
            source_event_type=event_name,
            delivery_kind="webhook",
            raw_payload=raw_body,
            content_type=request.headers.get("content-type", "application/json"),
            source_visibility=visibility,
            source_acl=source_acl,
            source_timestamp=_source_timestamp(event_name, payload),
        )
    except RawEventRejectedError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    canonical = canonicalize_raw_event(db, persisted.event)
    return {
        "ok": True,
        "created": persisted.created,
        "canonical_created": canonical.created,
        "quarantined": canonical.quarantined,
    }
