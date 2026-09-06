import base64
import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.canonical_events import canonicalize_raw_event
from app.config import Settings, get_settings
from app.database import get_db
from app.github import (
    GitHubAPIClient,
    GitHubAPIError,
    GitHubConfigurationError,
    GitHubTransportError,
    get_github_api_client,
)
from app.integrations import record_sync_failure, record_sync_success
from app.permissions import AuthorizationContext
from app.raw_events import persist_raw_event
from app.routes.github_common import get_github_connection, github_failure, manage_integrations
from app.schemas import GitHubBackfillRead, GitHubBackfillRequest

router = APIRouter(tags=["github"])

_RESOURCES = ("repository", "commits", "pull_requests", "issues", "deployments")


def _encode_cursor(
    *,
    connection_id: uuid.UUID,
    repository_id: int,
    resource: str,
    page: int,
    secret: str,
) -> str:
    payload = {
        "connection_id": str(connection_id),
        "repository_id": repository_id,
        "resource": resource,
        "page": page,
        "version": 1,
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    ).decode("ascii").rstrip("=")
    signature = hmac.new(secret.encode(), encoded.encode(), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def _decode_cursor(
    cursor: str,
    *,
    connection_id: uuid.UUID,
    secret: str,
) -> tuple[int, str, int]:
    try:
        encoded, supplied_signature = cursor.split(".", 1)
    except ValueError as exc:
        raise ValueError("Invalid GitHub backfill cursor") from exc
    expected_signature = hmac.new(
        secret.encode(), encoded.encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected_signature, supplied_signature):
        raise ValueError("Invalid GitHub backfill cursor")
    try:
        padded = encoded + ("=" * (-len(encoded) % 4))
        payload = json.loads(base64.urlsafe_b64decode(padded))
        if not isinstance(payload, dict):
            raise TypeError
        if payload.get("connection_id") != str(connection_id) or payload.get("version") != 1:
            raise ValueError
        repository_id = int(payload["repository_id"])
        resource = str(payload["resource"])
        page = int(payload["page"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid GitHub backfill cursor") from exc
    if resource not in _RESOURCES or page < 1 or repository_id < 1:
        raise ValueError("Invalid GitHub backfill cursor")
    return repository_id, resource, page


def _repository_visibility(repository: dict[str, object]) -> tuple[str, list[str]]:
    repository_id = repository.get("id")
    visibility = repository.get("visibility")
    private = repository.get("private") is True
    normalized = visibility if isinstance(visibility, str) else None
    if normalized == "public" or (normalized is None and not private):
        return "public_repository", []
    if isinstance(repository_id, int):
        return f"{normalized or 'private'}_repository", [
            f"github:repository:{repository_id}"
        ]
    return "restricted_repository", []


def _timestamp(item: dict[str, object], resource: str) -> datetime | None:
    candidates: list[object] = [item.get("updated_at"), item.get("created_at")]
    if resource == "commits":
        commit = item.get("commit")
        if isinstance(commit, dict):
            author = commit.get("author")
            committer = commit.get("committer")
            if isinstance(author, dict):
                candidates.insert(0, author.get("date"))
            if isinstance(committer, dict):
                candidates.insert(0, committer.get("date"))
    for value in candidates:
        if not isinstance(value, str) or not value:
            continue
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            continue
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return None


def _source_id(repository_id: int, resource: str, item: dict[str, object]) -> str:
    if resource == "repository":
        identifier = repository_id
    elif resource == "commits":
        identifier = item.get("sha")
    else:
        identifier = item.get("id") or item.get("number")
    if not isinstance(identifier, (str, int)) or not str(identifier):
        raise ValueError("GitHub backfill item has no stable identifier")
    singular = {
        "repository": "repository",
        "commits": "commit",
        "pull_requests": "pull_request",
        "issues": "issue",
        "deployments": "deployment",
    }[resource]
    return f"backfill:{singular}:{repository_id}:{identifier}"


def _source_type(resource: str) -> str:
    return {
        "repository": "backfill.repository",
        "commits": "backfill.commit",
        "pull_requests": "backfill.pull_request",
        "issues": "backfill.issue",
        "deployments": "backfill.deployment",
    }[resource]


def _next_resource(resource: str) -> str | None:
    index = _RESOURCES.index(resource)
    return _RESOURCES[index + 1] if index + 1 < len(_RESOURCES) else None


def _find_repository(
    repositories: list[dict[str, object]],
    repository_id: int,
) -> dict[str, object] | None:
    return next((item for item in repositories if item.get("id") == repository_id), None)


def _next_repository(
    repositories: list[dict[str, object]],
    repository_id: int,
) -> dict[str, object] | None:
    candidates = [
        item
        for item in repositories
        if isinstance(item.get("id"), int) and int(item["id"]) > repository_id
    ]
    return min(candidates, key=lambda item: int(item["id"])) if candidates else None


@router.post(
    "/organizations/{organization_id}/integrations/{connection_id}/github/backfill",
    response_model=GitHubBackfillRead,
)
def backfill_github(
    organization_id: uuid.UUID,
    connection_id: uuid.UUID,
    payload: GitHubBackfillRequest,
    authorization: Annotated[AuthorizationContext, Depends(manage_integrations)],
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[Session, Depends(get_db)],
    github_api: Annotated[GitHubAPIClient, Depends(get_github_api_client)],
) -> GitHubBackfillRead:
    del authorization
    connection = get_github_connection(
        db,
        organization_id=organization_id,
        connection_id=connection_id,
    )
    try:
        installation_id = int(connection.external_account_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="GitHub installation identifier is invalid",
        ) from exc

    try:
        installation_token = github_api.create_installation_token(installation_id)
        repositories = github_api.list_installation_repositories(installation_token)
    except (GitHubAPIError, GitHubTransportError, GitHubConfigurationError) as exc:
        record_sync_failure(db, connection, error_code=f"github_{getattr(exc, 'code', 'error')}")
        raise github_failure(exc) from exc

    if not repositories:
        record_sync_success(db, connection, cursor=None)
        return GitHubBackfillRead(
            inserted=0,
            duplicates=0,
            canonicalized=0,
            quarantined=0,
            next_cursor=None,
            complete=True,
            repository=None,
            resource=None,
        )

    cursor_value = None if payload.reset else payload.cursor or connection.sync_cursor
    if cursor_value:
        try:
            repository_id, resource, page = _decode_cursor(
                cursor_value,
                connection_id=connection.id,
                secret=settings.app_secret,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        repository = _find_repository(repositories, repository_id)
        if repository is None:
            repository = _next_repository(repositories, repository_id)
            if repository is None:
                record_sync_success(db, connection, cursor=None)
                return GitHubBackfillRead(
                    inserted=0,
                    duplicates=0,
                    canonicalized=0,
                    quarantined=0,
                    next_cursor=None,
                    complete=True,
                    repository=None,
                    resource=None,
                )
            repository_id = int(repository["id"])
            resource = "repository"
            page = 1
    else:
        repository = min(repositories, key=lambda item: int(item.get("id") or 0))
        repository_id = int(repository["id"])
        resource = "repository"
        page = 1

    full_name = repository.get("full_name")
    if not isinstance(full_name, str) or not full_name:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="GitHub repository has no full name",
        )

    visibility, source_acl = _repository_visibility(repository)
    if resource == "repository":
        raw_items = [repository]
        items = raw_items
    else:
        try:
            raw_items = github_api.list_resource_page(
                installation_token,
                full_name,
                resource,
                page=page,
                per_page=payload.page_size,
            )
        except (GitHubAPIError, GitHubTransportError, GitHubConfigurationError) as exc:
            record_sync_failure(
                db,
                connection,
                error_code=f"github_{getattr(exc, 'code', 'error')}",
            )
            raise github_failure(exc) from exc
        items = (
            [item for item in raw_items if "pull_request" not in item]
            if resource == "issues"
            else raw_items
        )

    inserted = 0
    duplicates = 0
    canonicalized = 0
    quarantined = 0
    for item in items:
        try:
            source_id = _source_id(repository_id, resource, item)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc),
            ) from exc
        raw_payload = json.dumps(
            {"repository": repository, "item": item},
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        persisted = persist_raw_event(
            db,
            organization_id=organization_id,
            integration_connection_id=connection_id,
            provider="github",
            source_event_id=source_id,
            source_event_type=_source_type(resource),
            delivery_kind="backfill",
            raw_payload=raw_payload,
            content_type="application/json",
            source_visibility=visibility,
            source_acl=source_acl,
            source_timestamp=_timestamp(item, resource),
        )
        canonical = canonicalize_raw_event(db, persisted.event)
        inserted += int(persisted.created)
        duplicates += int(not persisted.created)
        canonicalized += int(canonical.created)
        quarantined += int(canonical.quarantined)

    if resource == "repository":
        next_resource = "commits"
        next_page = 1
        next_repository = repository
    elif len(raw_items) >= payload.page_size:
        next_resource = resource
        next_page = page + 1
        next_repository = repository
    else:
        following_resource = _next_resource(resource)
        if following_resource is not None:
            next_resource = following_resource
            next_page = 1
            next_repository = repository
        else:
            following_repository = _next_repository(repositories, repository_id)
            if following_repository is None:
                next_cursor = None
                record_sync_success(db, connection, cursor=None)
                return GitHubBackfillRead(
                    inserted=inserted,
                    duplicates=duplicates,
                    canonicalized=canonicalized,
                    quarantined=quarantined,
                    next_cursor=None,
                    complete=True,
                    repository=full_name,
                    resource=resource,
                )
            next_resource = "repository"
            next_page = 1
            next_repository = following_repository

    next_repository_id = int(next_repository["id"])
    next_cursor = _encode_cursor(
        connection_id=connection.id,
        repository_id=next_repository_id,
        resource=next_resource,
        page=next_page,
        secret=settings.app_secret,
    )
    record_sync_success(db, connection, cursor=next_cursor)
    return GitHubBackfillRead(
        inserted=inserted,
        duplicates=duplicates,
        canonicalized=canonicalized,
        quarantined=quarantined,
        next_cursor=next_cursor,
        complete=False,
        repository=full_name,
        resource=resource,
    )
