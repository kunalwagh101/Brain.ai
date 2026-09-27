import json
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.embeddings import EmbeddingClient
from app.models import (
    CanonicalEvent,
    IntegrationConnection,
    Membership,
    MembershipRole,
    Organization,
    RawEvent,
    User,
)
from app.search import (
    SearchMode,
    process_embedding_batch,
    project_search_document,
    search_documents,
)

CONCEPTS = (
    ("authentication", "login"),
    ("postgres", "database"),
    ("launch", "release"),
    ("permissions", "access"),
    ("outage", "incident"),
)


class ConceptEmbeddingClient(EmbeddingClient):
    def embed(self, texts: list[str], *, model: str) -> list[list[float]]:
        del model
        vectors: list[list[float]] = []
        for text in texts:
            lowered = text.casefold()
            vectors.append(
                [
                    1.0 if any(term in lowered for term in pair) else 0.0
                    for pair in CONCEPTS
                ]
            )
        return vectors


def _seed_org(db: Session) -> tuple[Organization, User]:
    user = User(email="search-eval@example.com")
    org = Organization(name="Search Eval", slug="search-eval")
    db.add_all([user, org])
    db.flush()
    db.add(
        Membership(
            organization_id=org.id,
            user_id=user.id,
            role=MembershipRole.OWNER,
        )
    )
    db.commit()
    return org, user


def _add_public_github_evidence(
    db: Session,
    *,
    org: Organization,
    user: User,
    object_id: str,
    text: str,
) -> None:
    connection = IntegrationConnection(
        organization_id=org.id,
        provider="github",
        external_account_id=f"eval-{object_id}",
        display_name=f"Eval {object_id}",
        scopes=[],
        provider_metadata={},
        created_by_user_id=user.id,
    )
    db.add(connection)
    db.flush()

    payload = json.dumps(
        {
            "action": "opened",
            "repository": {"id": object_id, "full_name": "brain/eval"},
            "pull_request": {
                "id": object_id,
                "title": text,
                "body": text,
            },
        }
    ).encode()
    raw = RawEvent(
        organization_id=org.id,
        integration_connection_id=connection.id,
        provider="github",
        source_event_id=f"eval-source-{object_id}",
        source_event_type="pull_request",
        delivery_kind="webhook",
        source_timestamp=datetime.now(UTC),
        content_type="application/json",
        payload_sha256=(object_id * 64)[:64],
        raw_payload=payload,
        source_visibility="public_repository",
        source_acl=[],
    )
    db.add(raw)
    db.flush()

    event = CanonicalEvent(
        organization_id=org.id,
        raw_event_id=raw.id,
        integration_connection_id=connection.id,
        schema_version=1,
        event_type="pull_request.opened",
        action="opened",
        actor_type="github_user",
        actor_external_id="eval-user",
        actor_display_name="Eval User",
        object_type="pull_request",
        object_external_id=object_id,
        object_display_name=text,
        source_provider="github",
        source_event_id=raw.source_event_id,
        source_event_type=raw.source_event_type,
        occurred_at=datetime.now(UTC),
        source_visibility="public_repository",
        source_acl=[],
        provenance={"raw_event_id": str(raw.id)},
        event_metadata={
            "repository_id": object_id,
            "repository": "brain/eval",
        },
    )
    db.add(event)
    db.commit()
    project_search_document(db, event)


def test_hybrid_retrieval_synthetic_recall_at_3_is_at_least_90_percent(
    db_session: Session,
) -> None:
    org, user = _seed_org(db_session)
    documents = (
        ("101", "authentication architecture"),
        ("102", "postgres migration plan"),
        ("103", "launch checklist"),
        ("104", "permissions policy"),
        ("105", "outage response playbook"),
    )
    for object_id, text in documents:
        _add_public_github_evidence(
            db_session,
            org=org,
            user=user,
            object_id=object_id,
            text=text,
        )

    client = ConceptEmbeddingClient()
    embedded, failed = process_embedding_batch(
        db_session,
        embedding_client=client,
        model="synthetic-concepts-v1",
        limit=20,
    )
    assert (embedded, failed) == (len(documents), 0)

    evaluation = (
        ("login flow", "101"),
        ("database migration", "102"),
        ("release checklist", "103"),
        ("access policy", "104"),
        ("incident response", "105"),
    )
    relevant_found = 0
    for query, relevant_object_id in evaluation:
        result = search_documents(
            db_session,
            organization_id=org.id,
            user_id=user.id,
            query=query,
            mode=SearchMode.HYBRID,
            limit=3,
            embedding_client=client,
            embedding_model="synthetic-concepts-v1",
        )
        returned = {hit.document.object_external_id for hit in result.hits}
        if relevant_object_id in returned:
            relevant_found += 1

    recall_at_3 = relevant_found / len(evaluation)
    assert recall_at_3 >= 0.90

