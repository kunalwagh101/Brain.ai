import hashlib
import hmac
import json
import time
import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import Settings, get_settings
from app.main import app
from app.models import (
    IntegrationConnection,
    IntegrationHealth,
    IntegrationStatus,
    Membership,
    MembershipRole,
    Organization,
    RawEvent,
    SlackChannelAuthorization,
    User,
)
from app.secrets import get_secret_store
from app.slack import (
    SLACK_OAUTH_SCOPES,
    create_oauth_state,
    get_slack_api_client,
    verify_slack_request,
)


class FakeSecretStore:
    def __init__(self) -> None:
        self.stored: list[dict[str, object]] = []
        self.deleted: list[str] = []

    def store_connection_secret(
        self,
        *,
        organization_id: uuid.UUID,
        connection_id: uuid.UUID,
        provider: str,
        credentials: dict[str, str],
    ) -> str:
        self.stored.append(
            {
                "organization_id": organization_id,
                "connection_id": connection_id,
                "provider": provider,
                "credentials": credentials,
            }
        )
        return f"arn:secret:{connection_id}"

    def load_connection_secret(self, reference: str) -> dict[str, str]:
        return {"bot_token": "xoxb-test", "reference": reference}

    def schedule_delete(self, reference: str) -> None:
        self.deleted.append(reference)


class FakeSlackAPI:
    def __init__(self) -> None:
        self.last_state: str | None = None
        self.channel_info: dict[str, object] = {
            "channel": {
                "id": "C1",
                "name": "general",
                "is_private": False,
                "is_member": True,
            }
        }
        self.members = ["U1", "U2"]
        self.history_payload: dict[str, object] = {
            "ok": True,
            "messages": [],
            "response_metadata": {"next_cursor": ""},
        }

    def build_authorization_url(self, state: str) -> str:
        self.last_state = state
        return f"https://slack.example/oauth?state={state}"

    def exchange_code(self, code: str) -> dict[str, object]:
        assert code == "oauth-code"
        return {
            "ok": True,
            "access_token": "xoxb-real",
            "scope": ",".join(SLACK_OAUTH_SCOPES),
            "team": {"id": "T123", "name": "Acme Slack"},
        }

    def list_channels(self, token: str, *, cursor: str | None = None) -> dict[str, object]:
        assert token == "xoxb-test"
        return {
            "ok": True,
            "channels": [
                {
                    "id": "C1",
                    "name": "general",
                    "is_private": False,
                    "is_member": True,
                },
                {
                    "id": "G1",
                    "name": "leadership",
                    "is_private": True,
                    "is_member": True,
                },
            ],
            "response_metadata": {"next_cursor": cursor or ""},
        }

    def conversation_info(self, token: str, channel_id: str) -> dict[str, object]:
        assert token == "xoxb-test"
        channel = self.channel_info.get("channel")
        assert isinstance(channel, dict)
        channel["id"] = channel_id
        return self.channel_info

    def conversation_members(self, token: str, channel_id: str) -> list[str]:
        assert token == "xoxb-test"
        assert channel_id
        return list(self.members)

    def history(
        self,
        token: str,
        channel_id: str,
        *,
        cursor: str | None,
        limit: int,
    ) -> dict[str, object]:
        assert token == "xoxb-test"
        assert channel_id
        assert limit <= 15
        del cursor
        return self.history_payload


def _settings() -> Settings:
    return Settings(
        app_secret="test-app-secret",
        slack_client_id="client-id",
        slack_client_secret="client-secret",
        slack_signing_secret="test-signing-secret",
        slack_redirect_uri="http://testserver/api/v1/integrations/slack/oauth/callback",
    )


def _configure(
    *,
    user: User | None,
    store: FakeSecretStore,
    slack_api: FakeSlackAPI,
    settings: Settings,
) -> None:
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_secret_store] = lambda: store
    app.dependency_overrides[get_slack_api_client] = lambda: slack_api
    if user is not None:
        app.dependency_overrides[get_current_user] = lambda: user


def _seed_org(
    db: Session,
    *,
    role: MembershipRole = MembershipRole.OWNER,
    slug: str = "slack-acme",
) -> tuple[User, Organization]:
    user = User(email=f"{role.value}-{slug}@example.com")
    organization = Organization(name="Acme", slug=slug)
    db.add_all([user, organization])
    db.flush()
    db.add(Membership(organization_id=organization.id, user_id=user.id, role=role))
    db.commit()
    return user, organization


def _seed_connection(
    db: Session,
    organization: Organization,
    owner: User,
    *,
    workspace_id: str = "T123",
) -> IntegrationConnection:
    connection = IntegrationConnection(
        organization_id=organization.id,
        provider="slack",
        external_account_id=workspace_id,
        display_name="Acme Slack",
        status=IntegrationStatus.ACTIVE,
        health=IntegrationHealth.HEALTHY,
        scopes=list(SLACK_OAUTH_SCOPES),
        secret_ref="arn:secret:slack",
        created_by_user_id=owner.id,
    )
    db.add(connection)
    db.commit()
    return connection


def _sign(raw: bytes, timestamp: str, secret: str = "test-signing-secret") -> str:
    basestring = b"v0:" + timestamp.encode() + b":" + raw
    return "v0=" + hmac.new(secret.encode(), basestring, hashlib.sha256).hexdigest()


def _event_request(
    client: TestClient,
    envelope: dict[str, object],
    *,
    signature: str | None = None,
) :
    raw = json.dumps(envelope, separators=(",", ":")).encode()
    timestamp = str(int(time.time()))
    return client.post(
        "/api/v1/webhooks/slack/events",
        content=raw,
        headers={
            "content-type": "application/json",
            "x-slack-request-timestamp": timestamp,
            "x-slack-signature": signature or _sign(raw, timestamp),
        },
    ), raw


def test_oauth_install_and_callback_store_bot_token_outside_database(
    client: TestClient,
    db_session: Session,
) -> None:
    owner, organization = _seed_org(db_session)
    store = FakeSecretStore()
    slack_api = FakeSlackAPI()
    settings = _settings()
    _configure(user=owner, store=store, slack_api=slack_api, settings=settings)

    install = client.get(
        f"/api/v1/organizations/{organization.id}/integrations/slack/install"
    )
    assert install.status_code == 200
    assert set(install.json()["scopes"]) == set(SLACK_OAUTH_SCOPES)
    assert all(not scope.startswith(("im:", "mpim:")) for scope in install.json()["scopes"])

    state = create_oauth_state(
        organization_id=organization.id,
        user_id=owner.id,
        secret=settings.app_secret,
    )
    callback = client.get(
        "/api/v1/integrations/slack/oauth/callback",
        params={"code": "oauth-code", "state": state},
    )

    assert callback.status_code == 200
    assert callback.json()["external_account_id"] == "T123"
    assert "xoxb-real" not in callback.text
    connection = db_session.query(IntegrationConnection).one()
    assert connection.secret_ref.startswith("arn:secret:")
    assert store.stored[0]["credentials"] == {"bot_token": "xoxb-real"}


def test_private_channel_authorization_captures_source_membership(
    client: TestClient,
    db_session: Session,
) -> None:
    owner, organization = _seed_org(db_session)
    connection = _seed_connection(db_session, organization, owner)
    store = FakeSecretStore()
    slack_api = FakeSlackAPI()
    slack_api.channel_info = {
        "channel": {
            "id": "G1",
            "name": "leadership",
            "is_private": True,
            "is_member": True,
        }
    }
    _configure(user=owner, store=store, slack_api=slack_api, settings=_settings())

    response = client.post(
        f"/api/v1/organizations/{organization.id}/integrations/{connection.id}/"
        "slack/channels/G1/authorize"
    )

    assert response.status_code == 200
    assert response.json()["is_private"] is True
    assert response.json()["member_ids"] == ["U1", "U2"]


def test_dm_channel_cannot_be_authorized(client: TestClient, db_session: Session) -> None:
    owner, organization = _seed_org(db_session)
    connection = _seed_connection(db_session, organization, owner)
    store = FakeSecretStore()
    slack_api = FakeSlackAPI()
    slack_api.channel_info = {
        "channel": {
            "id": "D1",
            "name": "dm",
            "is_im": True,
            "is_member": True,
        }
    }
    _configure(user=owner, store=store, slack_api=slack_api, settings=_settings())

    response = client.post(
        f"/api/v1/organizations/{organization.id}/integrations/{connection.id}/"
        "slack/channels/D1/authorize"
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Slack DMs are not supported"}


def test_signed_authorized_event_is_stored_once_with_exact_payload(
    client: TestClient,
    db_session: Session,
) -> None:
    owner, organization = _seed_org(db_session)
    connection = _seed_connection(db_session, organization, owner)
    channel = SlackChannelAuthorization(
        organization_id=organization.id,
        integration_connection_id=connection.id,
        channel_id="G1",
        channel_name="leadership",
        is_private=True,
        member_ids=["U1", "U2"],
        authorized_by_user_id=owner.id,
    )
    db_session.add(channel)
    db_session.commit()
    _configure(
        user=None,
        store=FakeSecretStore(),
        slack_api=FakeSlackAPI(),
        settings=_settings(),
    )
    envelope = {
        "type": "event_callback",
        "team_id": "T123",
        "event_id": "Ev-1",
        "event_time": int(time.time()),
        "event": {
            "type": "message",
            "channel": "G1",
            "user": "U1",
            "text": "ship it",
            "ts": "1788696000.000001",
        },
    }

    first, raw = _event_request(client, envelope)
    second, _ = _event_request(client, envelope)

    assert first.status_code == 200
    assert first.json()["created"] is True
    assert second.status_code == 200
    assert second.json()["created"] is False
    event = db_session.query(RawEvent).one()
    assert event.raw_payload == raw
    assert event.source_visibility == "private_channel"
    assert event.source_acl == ["U1", "U2"]


def test_invalid_signature_is_rejected_before_storage(
    client: TestClient,
    db_session: Session,
) -> None:
    _configure(
        user=None,
        store=FakeSecretStore(),
        slack_api=FakeSlackAPI(),
        settings=_settings(),
    )
    response, _ = _event_request(
        client,
        {"type": "event_callback", "team_id": "T123", "event_id": "Ev-bad"},
        signature="v0=bad",
    )

    assert response.status_code == 401
    assert db_session.query(RawEvent).count() == 0


def test_url_verification_requires_valid_signature(client: TestClient) -> None:
    _configure(
        user=None,
        store=FakeSecretStore(),
        slack_api=FakeSlackAPI(),
        settings=_settings(),
    )
    response, _ = _event_request(
        client,
        {"type": "url_verification", "challenge": "challenge-123"},
    )

    assert response.status_code == 200
    assert response.json() == {"challenge": "challenge-123"}


def test_unapproved_channel_is_ignored(client: TestClient, db_session: Session) -> None:
    owner, organization = _seed_org(db_session)
    _seed_connection(db_session, organization, owner)
    _configure(
        user=None,
        store=FakeSecretStore(),
        slack_api=FakeSlackAPI(),
        settings=_settings(),
    )
    envelope = {
        "type": "event_callback",
        "team_id": "T123",
        "event_id": "Ev-unapproved",
        "event_time": int(time.time()),
        "event": {"type": "message", "channel": "C-not-approved", "ts": "1.0"},
    }

    response, _ = _event_request(client, envelope)

    assert response.status_code == 200
    assert response.json()["ignored"] == "channel_not_authorized"
    assert db_session.query(RawEvent).count() == 0


def test_private_membership_event_updates_source_acl_state(
    client: TestClient,
    db_session: Session,
) -> None:
    owner, organization = _seed_org(db_session)
    connection = _seed_connection(db_session, organization, owner)
    channel = SlackChannelAuthorization(
        organization_id=organization.id,
        integration_connection_id=connection.id,
        channel_id="G1",
        channel_name="leadership",
        is_private=True,
        member_ids=["U1", "U2"],
        authorized_by_user_id=owner.id,
    )
    db_session.add(channel)
    db_session.commit()
    _configure(
        user=None,
        store=FakeSecretStore(),
        slack_api=FakeSlackAPI(),
        settings=_settings(),
    )
    envelope = {
        "type": "event_callback",
        "team_id": "T123",
        "event_id": "Ev-member-left",
        "event_time": int(time.time()),
        "event": {"type": "member_left_channel", "channel": "G1", "user": "U2"},
    }

    response, _ = _event_request(client, envelope)

    assert response.status_code == 200
    db_session.refresh(channel)
    assert channel.member_ids == ["U1"]
    assert db_session.query(RawEvent).count() == 1


def test_backfill_is_resumable_and_replay_safe(
    client: TestClient,
    db_session: Session,
) -> None:
    owner, organization = _seed_org(db_session)
    connection = _seed_connection(db_session, organization, owner)
    channel = SlackChannelAuthorization(
        organization_id=organization.id,
        integration_connection_id=connection.id,
        channel_id="G1",
        channel_name="leadership",
        is_private=True,
        member_ids=["U1", "U2"],
        authorized_by_user_id=owner.id,
    )
    db_session.add(channel)
    db_session.commit()
    store = FakeSecretStore()
    slack_api = FakeSlackAPI()
    slack_api.history_payload = {
        "ok": True,
        "messages": [
            {"type": "message", "user": "U1", "text": "one", "ts": "10.000001"},
            {"type": "message", "user": "U2", "text": "two", "ts": "9.000001"},
        ],
        "response_metadata": {"next_cursor": "cursor-2"},
    }
    _configure(user=owner, store=store, slack_api=slack_api, settings=_settings())
    url = (
        f"/api/v1/organizations/{organization.id}/integrations/{connection.id}/"
        "slack/channels/G1/backfill"
    )

    first = client.post(url, json={})
    assert first.status_code == 200
    assert first.json()["inserted"] == 2
    assert first.json()["next_cursor"] == "cursor-2"
    db_session.refresh(channel)
    assert channel.backfill_cursor == "cursor-2"

    slack_api.history_payload = {
        "ok": True,
        "messages": [
            {"type": "message", "user": "U1", "text": "one", "ts": "10.000001"},
            {"type": "message", "user": "U2", "text": "two", "ts": "9.000001"},
        ],
        "response_metadata": {"next_cursor": ""},
    }
    replay = client.post(url, json={"reset": True})

    assert replay.status_code == 200
    assert replay.json()["inserted"] == 0
    assert replay.json()["duplicates"] == 2
    assert replay.json()["complete"] is True
    assert db_session.query(RawEvent).count() == 2


def test_signature_replay_window_rejects_old_timestamp() -> None:
    raw = b"{}"
    timestamp = "1000"
    signature = _sign(raw, timestamp)

    assert verify_slack_request(
        raw,
        timestamp=timestamp,
        signature=signature,
        signing_secret="test-signing-secret",
        now_epoch=1000,
    )
    assert not verify_slack_request(
        raw,
        timestamp=timestamp,
        signature=signature,
        signing_secret="test-signing-secret",
        now_epoch=1301,
    )


def test_oauth_state_is_tamper_evident() -> None:
    state = create_oauth_state(
        organization_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        secret="state-secret",
        now=datetime(2026, 9, 6, tzinfo=UTC),
    )
    payload, signature = state.split(".", 1)
    tampered = f"{payload[:-1]}A.{signature}"

    from app.slack import verify_oauth_state

    try:
        verify_oauth_state(
            tampered,
            secret="state-secret",
            now=datetime(2026, 9, 6, tzinfo=UTC),
        )
    except ValueError:
        pass
    else:
        raise AssertionError("Tampered Slack OAuth state must be rejected")
