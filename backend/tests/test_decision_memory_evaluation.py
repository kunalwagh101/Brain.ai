import pytest

from app.decision_memory import extract_decision_blocker_candidates
from app.decision_memory_models import MemoryKind
from app.search_models import SearchDocument

_CASES: tuple[tuple[str, set[MemoryKind]], ...] = (
    ("Decision: use PostgreSQL as the primary store", {MemoryKind.DECISION}),
    ("Final decision: keep the modular monolith", {MemoryKind.DECISION}),
    ("We decided to ship the migration behind a flag", {MemoryKind.DECISION}),
    ("The decision is to keep customer data in-region", {MemoryKind.DECISION}),
    ("We agreed to require explicit approval for mutations", {MemoryKind.DECISION}),
    ("Blocker: production credentials are missing", {MemoryKind.BLOCKER}),
    ("We are blocked by the provider outage", {MemoryKind.BLOCKER}),
    ("Deployment is blocked by an incomplete security review", {MemoryKind.BLOCKER}),
    ("Blocked because the schema migration failed", {MemoryKind.BLOCKER}),
    ("We cannot proceed until legal approves the DPA", {MemoryKind.BLOCKER}),
    ("We're waiting on the GitHub App installation", {MemoryKind.BLOCKER}),
    ("Status: PostgreSQL migration is 80 percent complete", set()),
    ("We considered Redis but have not chosen it", set()),
    ("A decision may be needed next week", set()),
    ("Potential blocker discussed in planning", set()),
    ("The provider outage was resolved yesterday", set()),
    ("Waiting room support was released", set()),
    ("The team reviewed three architecture options", set()),
    ("No blocker exists for the release", set()),
    ("The pull request is ready for review", set()),
)


@pytest.mark.parametrize("kind", [MemoryKind.DECISION, MemoryKind.BLOCKER])
def test_synthetic_explicit_marker_precision_is_at_least_ninety_percent(
    kind: MemoryKind,
) -> None:
    true_positive = 0
    false_positive = 0
    for text, expected in _CASES:
        document = SearchDocument(title="", content=text, is_deleted=False)
        emitted = extract_decision_blocker_candidates(document)
        for candidate in emitted:
            if candidate.kind != kind:
                continue
            if kind in expected:
                true_positive += 1
            else:
                false_positive += 1

    precision = true_positive / max(1, true_positive + false_positive)
    assert precision >= 0.90


def test_synthetic_fixture_contains_both_positive_and_negative_examples() -> None:
    assert any(MemoryKind.DECISION in expected for _, expected in _CASES)
    assert any(MemoryKind.BLOCKER in expected for _, expected in _CASES)
    assert any(not expected for _, expected in _CASES)

