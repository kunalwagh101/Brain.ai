import json
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.embeddings import EmbeddingClient, EmbeddingError
from app.models import (
    CanonicalEvent,
    IntegrationConnection,
    Membership,
    MembershipRole,
    Organization,
    RawEvent,
    ResourceAccessLevel,
    ResourceGrant,
    SlackChannelAuthorization,
    SourceIdentity,
    SourceIdentityState,
    User,
)
from app.search import (
    SearchMode,
    process_embedding_batch,
    project_search_document,
    search_documents,
)
from app.search_models import SearchEmbeddingStatus
from app.work_graph import project_canonical_event


class FakeEmbeddingClient(EmbeddingClient):
    def embed(self, texts: list[str], *, model: str) -> list[list[float]]:
        del model
        vectors = []
        for text in texts:
            lowered = text.casefold()
            vectors.append([
                1.0 if "authentication" in lowered or "login" in lowered else 0.0,
                1.0 if "database" in lowered or "postgres" in lowered else 0.0,
                1.0 if "launch" in lowered or "release" in lowered else 0.0,
            ])
        return vectors


class FailingEmbeddingClient(EmbeddingClient):
    def embed(self, texts: list[str], *, model: str) -> list[list[float]]:
        del texts, model
        raise EmbeddingError("provider_down")


def _seed(db: Session, suffix: str):
    owner = User(email=f"owner-{suffix}@example.com")
    member = User(email=f"member-{suffix}@example.com")
    org = Organization(name=f"Org {suffix}", slug=f"org-{suffix}")
    db.add_all([owner, member, org])
    db.flush()
    db.add_all([
        Membership(organization_id=org.id, user_id=owner.id, role=MembershipRole.OWNER),
        Membership(organization_id=org.id, user_id=member.id, role=MembershipRole.MEMBER),
    ])
    db.commit()
    return org, owner, member


def _event(
    db: Session,
    *,
    org: Organization,
    owner: User,
    provider: str,
    visibility: str,
    object_id: str,
    text: str,
    channel_id: str | None = None,
    repository_id: str | None = None,
    action: str = "created",
) -> CanonicalEvent:
    connection = IntegrationConnection(
        organization_id=org.id,
        provider=provider,
        external_account_id=f"{provider}-{object_id}",
        display_name=f"{provider} {object_id}",
        scopes=[],
        provider_metadata={},
        created_by_user_id=owner.id,
    )
    db.add(connection)
    db.flush()
    if provider == "slack":
        payload = json.dumps(
            {
                "event": {
                    "channel": channel_id,
                    "type": "message",
                    "text": text,
                    "ts": "1.0",
                    "user": "U1",
                }
            }
        ).encode()
    else:
        payload = json.dumps(
            {
                "action": "opened",
                "repository": {
                    "id": int(repository_id or "1"),
                    "full_name": "acme/repo",
                },
                "pull_request": {"id": 1, "title": text, "body": text},
            }
        ).encode()
    raw = RawEvent(
        organization_id=org.id,
        integration_connection_id=connection.id,
        provider=provider,
        source_event_id=f"source-{object_id}-{action}",
        source_event_type="message" if provider == "slack" else "pull_request",
        delivery_kind="webhook",
        source_timestamp=datetime.now(UTC),
        content_type="application/json",
        payload_sha256="a" * 64,
        raw_payload=payload,
        source_visibility=visibility,
        source_acl=[f"github:repository:{repository_id}"] if repository_id else [],
    )
    db.add(raw)
    db.flush()
    event = CanonicalEvent(
        organization_id=org.id,
        raw_event_id=raw.id,
        integration_connection_id=connection.id,
        schema_version=1,
        event_type=f"message.{action}" if provider == "slack" else f"pull_request.{action}",
        action=action,
        actor_type=f"{provider}_user",
        actor_external_id="U1",
        actor_display_name="User",
        object_type="message" if provider == "slack" else "pull_request",
        object_external_id=object_id,
        object_display_name=text,
        source_provider=provider,
        source_event_id=raw.source_event_id,
        source_event_type=raw.source_event_type,
        occurred_at=datetime.now(UTC),
        source_visibility=visibility,
        source_acl=list(raw.source_acl),
        provenance={"raw_event_id": str(raw.id)},
        event_metadata={
            "channel_id": channel_id,
            "repository_id": repository_id,
            "repository": "acme/repo" if repository_id else None,
            "text": text if provider == "slack" else None,
        },
    )
    db.add(event)
    db.commit()
    project_canonical_event(db, event)
    return event


def test_keyword_search_is_tenant_scoped_and_requires_live_public_slack_authorization(
    db_session: Session,
) -> None:
    org, owner, member = _seed(db_session, "tenant-a")
    other_org, other_owner, _ = _seed(db_session, "tenant-b")
    event = _event(
        db_session, org=org, owner=owner, provider="slack", visibility="public_channel",
        object_id="C1:1", text="authentication middleware merged", channel_id="C1",
    )
    other = _event(
        db_session, org=other_org, owner=other_owner, provider="slack", visibility="public_channel",
        object_id="C2:1", text="authentication secret from other org", channel_id="C2",
    )
    project_search_document(db_session, event)
    project_search_document(db_session, other)

    assert search_documents(
        db_session, organization_id=org.id, user_id=member.id, query="authentication",
        mode=SearchMode.KEYWORD, limit=10, embedding_client=None, embedding_model=None,
    ).hits == []

    db_session.add(SlackChannelAuthorization(
        organization_id=org.id,
        integration_connection_id=event.integration_connection_id,
        channel_id="C1",
        channel_name="general",
        is_private=False,
        member_ids=[],
        authorized_by_user_id=owner.id,
    ))
    db_session.commit()
    hits = search_documents(
        db_session, organization_id=org.id, user_id=member.id, query="authentication",
        mode=SearchMode.KEYWORD, limit=10, embedding_client=None, embedding_model=None,
    ).hits
    assert [hit.document.canonical_event_id for hit in hits] == [event.id]


def test_private_slack_search_uses_current_resolved_membership(db_session: Session) -> None:
    org, owner, member = _seed(db_session, "private")
    event = _event(
        db_session, org=org, owner=owner, provider="slack", visibility="private_channel",
        object_id="CP:1", text="database launch blocker", channel_id="CP",
    )
    project_search_document(db_session, event)
    auth = SlackChannelAuthorization(
        organization_id=org.id,
        integration_connection_id=event.integration_connection_id,
        channel_id="CP",
        channel_name="private",
        is_private=True,
        member_ids=["U-MEMBER"],
        authorized_by_user_id=owner.id,
    )
    identity = SourceIdentity(
        organization_id=org.id,
        provider="slack",
        external_id="U-MEMBER",
        display_name="Member",
        email=None,
        email_verified=False,
        state=SourceIdentityState.RESOLVED,
        resolved_user_id=member.id,
        resolution_method="manual",
        first_seen_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
    )
    db_session.add_all([auth, identity])
    db_session.commit()
    assert len(search_documents(
        db_session, organization_id=org.id, user_id=member.id, query="blocker",
        mode=SearchMode.KEYWORD, limit=10, embedding_client=None, embedding_model=None,
    ).hits) == 1
    auth.member_ids = []
    db_session.commit()
    assert search_documents(
        db_session, organization_id=org.id, user_id=member.id, query="blocker",
        mode=SearchMode.KEYWORD, limit=10, embedding_client=None, embedding_model=None,
    ).hits == []


def test_private_github_requires_explicit_grant_even_for_owner(db_session: Session) -> None:
    org, owner, _ = _seed(db_session, "github-private")
    event = _event(
        db_session, org=org, owner=owner, provider="github", visibility="private_repository",
        object_id="PR-1", text="authentication login redesign", repository_id="77",
    )
    document = project_search_document(db_session, event)
    assert search_documents(
        db_session, organization_id=org.id, user_id=owner.id, query="login",
        mode=SearchMode.KEYWORD, limit=10, embedding_client=None, embedding_model=None,
    ).hits == []
    db_session.add(ResourceGrant(
        organization_id=org.id,
        resource_type="github.repository",
        resource_id="77",
        user_id=owner.id,
        access=ResourceAccessLevel.READ,
        created_by_user_id=owner.id,
    ))
    db_session.commit()
    hits = search_documents(
        db_session, organization_id=org.id, user_id=owner.id, query="login",
        mode=SearchMode.KEYWORD, limit=10, embedding_client=None, embedding_model=None,
    ).hits
    assert [hit.document.id for hit in hits] == [document.id]


def test_revoked_integration_and_delete_event_remove_results(db_session: Session) -> None:
    org, owner, _ = _seed(db_session, "revoke")
    event = _event(
        db_session, org=org, owner=owner, provider="github", visibility="public_repository",
        object_id="PR-2", text="release launch plan", repository_id="88",
    )
    document = project_search_document(db_session, event)
    assert len(search_documents(
        db_session, organization_id=org.id, user_id=owner.id, query="launch",
        mode=SearchMode.KEYWORD, limit=10, embedding_client=None, embedding_model=None,
    ).hits) == 1
    connection = db_session.get(IntegrationConnection, event.integration_connection_id)
    connection.status = "revoked"
    db_session.commit()
    assert search_documents(
        db_session, organization_id=org.id, user_id=owner.id, query="launch",
        mode=SearchMode.KEYWORD, limit=10, embedding_client=None, embedding_model=None,
    ).hits == []
    connection.status = "active"
    db_session.commit()
    event.action = "deleted"
    event.event_type = "pull_request.deleted"
    db_session.commit()
    project_search_document(db_session, event)
    assert document.is_deleted is True
    assert search_documents(
        db_session, organization_id=org.id, user_id=owner.id, query="launch",
        mode=SearchMode.KEYWORD, limit=10, embedding_client=None, embedding_model=None,
    ).hits == []


def test_hybrid_semantic_retrieval_and_degraded_fallback(db_session: Session) -> None:
    org, owner, _ = _seed(db_session, "semantic")
    event = _event(
        db_session, org=org, owner=owner, provider="github", visibility="public_repository",
        object_id="PR-3", text="authentication architecture", repository_id="99",
    )
    document = project_search_document(db_session, event)
    embedded, failed = process_embedding_batch(
        db_session, embedding_client=FakeEmbeddingClient(), model="fake-v1", limit=10,
    )
    assert (embedded, failed) == (1, 0)
    assert document.embedding_status == SearchEmbeddingStatus.READY

    result = search_documents(
        db_session, organization_id=org.id, user_id=owner.id, query="login",
        mode=SearchMode.HYBRID, limit=10,
        embedding_client=FakeEmbeddingClient(), embedding_model="fake-v1",
    )
    assert result.semantic_status == "ready"
    assert [hit.document.id for hit in result.hits] == [document.id]

    degraded = search_documents(
        db_session, organization_id=org.id, user_id=owner.id, query="authentication",
        mode=SearchMode.HYBRID, limit=10,
        embedding_client=FailingEmbeddingClient(), embedding_model="fake-v1",
    )
    assert degraded.semantic_status == "degraded"
    assert [hit.document.id for hit in degraded.hits] == [document.id]


def test_embedding_failure_is_retryable_and_does_not_duplicate_projection(
    db_session: Session,
) -> None:
    org, owner, _ = _seed(db_session, "retry")
    event = _event(
        db_session, org=org, owner=owner, provider="github", visibility="public_repository",
        object_id="PR-4", text="postgres database migration", repository_id="101",
    )
    first = project_search_document(db_session, event)
    second = project_search_document(db_session, event)
    assert first.id == second.id
    embedded, failed = process_embedding_batch(
        db_session, embedding_client=FailingEmbeddingClient(), model="fake-v1", limit=10,
    )
    assert (embedded, failed) == (0, 1)
    assert first.embedding_status == SearchEmbeddingStatus.FAILED
    assert first.embedding_attempts == 1
    assert first.next_retry_at is not None
