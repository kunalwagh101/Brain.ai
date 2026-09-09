import uuid
from types import SimpleNamespace

from app.ask_brain import MAX_CITATION_EXCERPT_CHARS, _bounded_evidence
from app.search import SearchResponseData


def test_citation_excerpt_is_bounded_and_matches_authorised_model_context() -> None:
    content = "supporting evidence " * 500
    document = SimpleNamespace(
        id=uuid.uuid4(),
        canonical_event_id=uuid.uuid4(),
        source_provider="github",
        provenance={"source_event_id": "evt-1"},
        object_type="pull_request",
        object_external_id="123",
        title="Authentication middleware merged",
        content=content,
        occurred_at=None,
    )
    search_result = SearchResponseData(
        hits=[SimpleNamespace(document=document)],
        semantic_status="not_requested",
    )

    evidence, citations = _bounded_evidence(search_result)

    assert len(evidence) == 1
    assert list(citations) == ["E1"]
    assert citations["E1"].excerpt == evidence[0]["content"][:MAX_CITATION_EXCERPT_CHARS]
    assert len(citations["E1"].excerpt) <= MAX_CITATION_EXCERPT_CHARS
