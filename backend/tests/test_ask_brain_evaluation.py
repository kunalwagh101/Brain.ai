from pathlib import Path

from app.ask_brain_evaluation import (
    CitationPairReview,
    ObservedCitationPair,
    evaluate_case,
    score_semantic_reviews,
    summarize_evaluation,
)


def test_automatic_gate_enforces_retrieval_target_without_claiming_semantics() -> None:
    supporting = [f"event-{index}" for index in range(10)]
    case = evaluate_case(
        case_id="retrieval-gate",
        expected_status="answer",
        actual_status="answer",
        supporting_canonical_event_ids=supporting,
        forbidden_canonical_event_ids=[],
        retrieved_canonical_event_ids=supporting[:9],
        cited_canonical_event_ids=[supporting[0]],
    )

    summary = summarize_evaluation([case], dataset_eligible=True)

    assert summary.retrieval_recall == 0.90
    assert summary.citation_target_precision == 1.0
    assert summary.automatic_gate_passed
    assert summary.semantic_review_required
    assert not summary.production_passed


def test_automatic_gate_fails_below_retrieval_target() -> None:
    case = evaluate_case(
        case_id="below-gate",
        expected_status="answer",
        actual_status="answer",
        supporting_canonical_event_ids=["event-a", "event-b"],
        forbidden_canonical_event_ids=[],
        retrieved_canonical_event_ids=["event-a"],
        cited_canonical_event_ids=["event-a"],
    )

    summary = summarize_evaluation([case], dataset_eligible=True)

    assert summary.retrieval_recall == 0.5
    assert not summary.automatic_gate_passed


def test_automatic_gate_fails_on_forbidden_evidence() -> None:
    case = evaluate_case(
        case_id="leakage",
        expected_status="answer",
        actual_status="answer",
        supporting_canonical_event_ids=["event-a"],
        forbidden_canonical_event_ids=["secret-event"],
        retrieved_canonical_event_ids=["event-a", "secret-event"],
        cited_canonical_event_ids=["event-a"],
    )

    summary = summarize_evaluation([case], dataset_eligible=True)

    assert summary.forbidden_exposures == 1
    assert not summary.automatic_gate_passed


def test_example_dataset_cannot_clear_automatic_production_gate() -> None:
    case = evaluate_case(
        case_id="synthetic",
        expected_status="answer",
        actual_status="answer",
        supporting_canonical_event_ids=["event-a"],
        forbidden_canonical_event_ids=[],
        retrieved_canonical_event_ids=["event-a"],
        cited_canonical_event_ids=["event-a"],
    )

    summary = summarize_evaluation([case], dataset_eligible=False)

    assert summary.retrieval_recall == 1.0
    assert not summary.automatic_gate_passed
    assert not summary.production_passed


def test_answer_on_labelled_no_answer_case_fails_safety_gate() -> None:
    case = evaluate_case(
        case_id="should-refuse",
        expected_status="insufficient_evidence",
        actual_status="answer",
        supporting_canonical_event_ids=["weak-event"],
        forbidden_canonical_event_ids=[],
        retrieved_canonical_event_ids=["weak-event"],
        cited_canonical_event_ids=["weak-event"],
    )

    summary = summarize_evaluation([case], dataset_eligible=True)

    assert summary.unsafe_answers == 1
    assert not summary.automatic_gate_passed


def test_human_review_is_required_for_real_citation_correctness() -> None:
    observed = [
        ObservedCitationPair("case-a", index, 0, f"event-{index}")
        for index in range(100)
    ]
    reviews = [
        CitationPairReview(
            "case-a",
            index,
            0,
            f"event-{index}",
            supported=index < 98,
        )
        for index in range(100)
    ]

    summary = score_semantic_reviews(
        observed,
        reviews,
        dataset_eligible=True,
        automatic_gate_passed=True,
    )

    assert summary.citation_correctness == 0.98
    assert summary.review_complete
    assert summary.production_passed


def test_incomplete_or_mismatched_human_review_cannot_pass() -> None:
    observed = [ObservedCitationPair("case-a", 0, 0, "event-a")]
    mismatched = [CitationPairReview("case-a", 0, 0, "event-b", supported=True)]

    summary = score_semantic_reviews(
        observed,
        mismatched,
        dataset_eligible=True,
        automatic_gate_passed=True,
    )

    assert summary.mismatched_evidence == 1
    assert not summary.review_complete
    assert not summary.production_passed


def test_sensitive_evaluation_directories_are_gitignored() -> None:
    repository_root = Path(__file__).resolve().parents[2]
    gitignore = (repository_root / ".gitignore").read_text(encoding="utf-8")

    assert "/.local/" in gitignore
    assert "/.evaluation/" in gitignore
