import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

import app.routes.search as search_route
from app.auth import get_current_user
from app.main import app
from app.models import Membership, MembershipRole, Organization, User
from app.search import SearchHit, SearchResponseData


def test_search_api_preserves_source_provenance_on_every_returned_result(
    client: TestClient,
    db_session: Session,
    monkeypatch,
) -> None:
    user = User(email="search-contract@example.com")
    organization = Organization(name="Search Contract", slug="search-contract")
    db_session.add_all([user, organization])
    db_session.flush()
    db_session.add(
        Membership(
            organization_id=organization.id,
            user_id=user.id,
            role=MembershipRole.MEMBER,
        )
    )
    db_session.commit()

    document_id = uuid.uuid4()
    event_id = uuid.uuid4()
    document = SimpleNamespace(
        id=document_id,
        canonical_event_id=event_id,
        source_provider="github",
        object_type="pull_request",
        object_external_id="PR-42",
        title="Permission-aware search",
        content="Search results retain their source evidence.",
        occurred_at=datetime.now(UTC),
        provenance={
            "source_event_id": "github-event-42",
            "source_event_type": "pull_request",
            "raw_event_id": str(uuid.uuid4()),
        },
    )
    monkeypatch.setattr(
        search_route,
        "build_embedding_client",
        lambda: (None, None),
    )
    monkeypatch.setattr(
        search_route,
        "search_documents",
        lambda *args, **kwargs: SearchResponseData(
            hits=[SearchHit(document=document, score=1.0)],
            semantic_status="not_requested",
        ),
    )
    app.dependency_overrides[get_current_user] = lambda: user
    try:
        response = client.get(
            f"/api/v1/organizations/{organization.id}/search",
            params={"q": "permission", "mode": "keyword"},
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["document_id"] == str(document_id)
    assert result["canonical_event_id"] == str(event_id)
    assert result["source_event_id"] == "github-event-42"
    assert result["provenance"]["source_event_id"] == "github-event-42"
    assert result["provenance"]["source_event_type"] == "pull_request"
    assert result["provenance"]["raw_event_id"]
