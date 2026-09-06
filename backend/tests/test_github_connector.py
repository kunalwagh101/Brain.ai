import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import Settings, get_settings
from app.github import (
    create_install_state,
    create_selection_token,
    get_github_api_client,
    verify_github_webhook,
    verify_install_state,
    verify_selection_token,
)
from app.main import app
from app.models import (
    CanonicalEvent,
    IntegrationConnection,
    IntegrationHealth,
    IntegrationStatus,
    Membership,
    MembershipRole,
    Organization,
    RawEvent,
    User,
)
from app.routes.github_backfill import _decode_cursor, _encode_cursor
from app.secrets import get_secret_store


class FakeSecretStore:
    def load_connection_secret(self, reference: str) -> dict[str, str]:
        assert reference == "arn:test:github-app"
        return {
            "private_key_pem": "not-used-by-webhook-test",
            "client_secret": "github-client-secret",
            "webhook_secret": "github-webhook-secret",
        }


class FakeGitHubAPI:
    def create_installation_token(self, installation_id: int) -> str:
        assert installation_id == 9001
        return "short-lived-installation-token"

    def list_installation_repositories(self, token: str) -> list[dict[str, object]]:
        assert token == "short-lived-installation-token"
        return [
            {
                "id": 501,
                "full_name": "acme/private-repo",
                "private": True,
                "visibility": "private",
            }
        ]

    def list_resource_page(
        self,
        token: str,
        full_name: str,
        resource: str,
        *,
        page: int,
        per_page: int,
    ) -> list[dict[str, object]]:
        assert token == "short-lived-installation-token"
        assert full_name == "acme/private-repo"
        assert page == 1
        assert per_page == 2
        if resource == "commits":
            return [
                {
                    "sha": "abc123",
                    "html_url": "https://github.com/acme/private-repo/commit/abc123",
                    "author": {"id": 88, "login": "dev-one"},
                    "commit": {"author": {"date": "2026-09-06T10:00:00Z"}},
                }
            ]
        return []


def _settings() -> Settings:
    return Settings(
        app_secret="test-app-secret",
        github_app_id="12345",
        github_app_slug="brain-test-app",
        github_client_id="Iv1.test",
        github_callback_url="http://testserver/api/v1/integrations/github/oauth/callback",
        github_app_secret_ref="arn:test:github-app",
    )


def _seed_owner_and_connection(
    db: Session,
) -> tuple[User, Organization, IntegrationConnection]:
    owner = User(email="github-owner@example.com")
    organization = Organization(name="Acme", slug="github-acme")
    db.add_all([owner, organization])
    db.flush()
    db.add(
        Membership(
            organization_id=organization.id,
            user_id=owner.id,
            role=MembershipRole.OWNER,
        )
    )
    connection = IntegrationConnection(
        organization_id=organization.id,
        provider="github",
        external_account_id="9001",
        display_name="acme",
        status=IntegrationStatus.ACTIVE,
        health=IntegrationHealth.UNKNOWN,
        scopes=["permission:contents:read"],
        provider_metadata={"account_id": 77, "account_login": "acme"},
        secret_ref=None,
        created_by_user_id=owner.id,
    )
    db.add(connection)
    db.commit()
    return owner, organization, connection


def test_github_webhook_signature_uses_exact_body() -> None:
    raw = b'{"action":"opened"}'
    signature = "sha256=" + hmac.new(
        b"hook-secret", raw, hashlib.sha256
    ).hexdigest()

    assert verify_github_webhook(raw, signature=signature, secret="hook-secret") is True
    assert (
        verify_github_webhook(raw + b" ", signature=signature, secret="hook-secret")
        is False
    )


def test_install_and_selection_tokens_are_signed_expiring_and_bound() -> None:
    organization_id = uuid.uuid4()
    user_id = uuid.uuid4()
    now = datetime(2026, 9, 6, 12, 0, tzinfo=UTC)
    state = create_install_state(
        organization_id=organization_id,
        user_id=user_id,
        secret="state-secret",
        now=now,
    )

    assert verify_install_state(
        state,
        secret="state-secret",
        now=now + timedelta(minutes=5),
    ) == (organization_id, user_id)
    with pytest.raises(ValueError):
        verify_install_state(state + "tampered", secret="state-secret", now=now)
    with pytest.raises(ValueError):
        verify_install_state(
            state,
            secret="state-secret",
            now=now + timedelta(minutes=11),
        )

    selection = create_selection_token(
        organization_id=organization_id,
        user_id=user_id,
        installation={
            "id": 9001,
            "app_id": 12345,
            "account": {"id": 77, "login": "acme"},
            "target_type": "Organization",
            "repository_selection": "selected",
        },
        secret="state-secret",
    )
    decoded = verify_selection_token(selection, secret="state-secret")
    assert decoded["installation_id"] == 9001
    assert decoded["account_id"] == 77
    assert decoded["account_login"] == "acme"
    with pytest.raises(ValueError):
        verify_selection_token(selection + "tampered", secret="state-secret")


def test_backfill_cursor_is_bound_to_connection_and_tamper_evident() -> None:
    connection_id = uuid.uuid4()
    cursor = _encode_cursor(
        connection_id=connection_id,
        repository_id=501,
        resource="commits",
        page=3,
        secret="cursor-secret",
    )

    assert _decode_cursor(
        cursor,
        connection_id=connection_id,
        secret="cursor-secret",
    ) == (501, "commits", 3)
    with pytest.raises(ValueError):
        _decode_cursor(
            cursor,
            connection_id=uuid.uuid4(),
            secret="cursor-secret",
        )
    with pytest.raises(ValueError):
        _decode_cursor(
            cursor + "tampered",
            connection_id=connection_id,
            secret="cursor-secret",
        )


def test_signed_private_repo_webhook_is_exactly_once_and_acl_preserved(
    client: TestClient,
    db_session: Session,
) -> None:
    _, organization, connection = _seed_owner_and_connection(db_session)
    settings = _settings()
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_secret_store] = lambda: FakeSecretStore()

    payload = {
        "action": "opened",
        "installation": {"id": 9001},
        "sender": {"id": 88, "login": "dev-one"},
        "repository": {
            "id": 501,
            "full_name": "acme/private-repo",
            "private": True,
            "visibility": "private",
        },
        "pull_request": {
            "id": 7001,
            "number": 17,
            "title": "Tenant-safe search",
            "state": "open",
            "created_at": "2026-09-06T10:00:00Z",
        },
    }
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    signature = "sha256=" + hmac.new(
        b"github-webhook-secret", raw, hashlib.sha256
    ).hexdigest()
    headers = {
        "content-type": "application/json",
        "x-hub-signature-256": signature,
        "x-github-delivery": "delivery-501",
        "x-github-event": "pull_request",
    }

    first = client.post("/api/v1/webhooks/github/events", content=raw, headers=headers)
    second = client.post("/api/v1/webhooks/github/events", content=raw, headers=headers)

    assert first.status_code == 200
    assert first.json() == {
        "ok": True,
        "created": True,
        "canonical_created": True,
        "quarantined": False,
    }
    assert second.status_code == 200
    assert second.json()["created"] is False
    assert second.json()["canonical_created"] is False
    assert db_session.scalar(select(func.count()).select_from(RawEvent)) == 1
    assert db_session.scalar(select(func.count()).select_from(CanonicalEvent)) == 1
    event = db_session.scalar(select(CanonicalEvent))
    assert event is not None
    assert event.organization_id == organization.id
    assert event.integration_connection_id == connection.id
    assert event.source_visibility == "private_repository"
    assert event.source_acl == ["github:repository:501"]


def test_github_backfill_resumes_and_replay_is_idempotent(
    client: TestClient,
    db_session: Session,
) -> None:
    owner, organization, connection = _seed_owner_and_connection(db_session)
    settings = _settings()
    app.dependency_overrides[get_current_user] = lambda: owner
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_github_api_client] = lambda: FakeGitHubAPI()

    url = f"/api/v1/organizations/{organization.id}/integrations/{connection.id}/github/backfill"
    repository_page = client.post(url, json={"page_size": 2})

    assert repository_page.status_code == 200
    first = repository_page.json()
    assert first["inserted"] == 1
    assert first["canonicalized"] == 1
    assert first["resource"] == "repository"
    assert first["next_cursor"]

    commits_page = client.post(
        url,
        json={"cursor": first["next_cursor"], "page_size": 2},
    )
    assert commits_page.status_code == 200
    second = commits_page.json()
    assert second["inserted"] == 1
    assert second["canonicalized"] == 1
    assert second["resource"] == "commits"
    assert second["next_cursor"]

    replay = client.post(
        url,
        json={"cursor": first["next_cursor"], "page_size": 2},
    )
    assert replay.status_code == 200
    replay_body = replay.json()
    assert replay_body["inserted"] == 0
    assert replay_body["duplicates"] == 1
    assert replay_body["canonicalized"] == 0
    assert db_session.scalar(select(func.count()).select_from(RawEvent)) == 2
    assert db_session.scalar(select(func.count()).select_from(CanonicalEvent)) == 2


def test_generic_integration_endpoint_cannot_bypass_github_app_flow(
    client: TestClient,
    db_session: Session,
) -> None:
    owner, organization, _ = _seed_owner_and_connection(db_session)
    app.dependency_overrides[get_current_user] = lambda: owner

    response = client.post(
        f"/api/v1/organizations/{organization.id}/integrations",
        json={
            "provider": "github",
            "external_account_id": "spoofed-installation",
            "display_name": "Spoofed GitHub",
            "credentials": {"token": "must-not-be-used"},
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Use the verified GitHub App installation flow"}
