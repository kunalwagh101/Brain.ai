from collections.abc import Iterable
from dataclasses import dataclass

CITATION_CORRECTNESS_TARGET = 0.98
RETRIEVAL_RECALL_TARGET = 0.90
_VALID_STATUSES = frozenset({"answer", "insufficient_evidence"})


@dataclass(frozen=True, slots=True)
class AskBrainCaseEvaluation:
    case_id: str
    expected_status: str
    actual_status: str
    expected_relevant: int
    retrieved_relevant: int
    citation_targets_total: int
    citation_targets_relevant: int
    unresolved_citations: int
    forbidden_exposures: int
    status_matches: bool
    contract_failure: bool
    unsafe_answer: bool


@dataclass(frozen=True, slots=True)
class AskBrainEvaluationSummary:
    cases: int
    retrieval_recall: float
    citation_target_precision: float
    status_accuracy: float
    forbidden_exposures: int
    contract_failures: int
    unsafe_answers: int
    dataset_eligible: bool
    automatic_gate_passed: bool
    semantic_review_required: bool
    production_passed: bool


@dataclass(frozen=True, slots=True)
class ObservedCitationPair:
    case_id: str
    claim_index: int
    citation_index: int
    canonical_event_id: str


@dataclass(frozen=True, slots=True)
class CitationPairReview:
    case_id: str
    claim_index: int
    citation_index: int
    canonical_event_id: str
    supported: bool


@dataclass(frozen=True, slots=True)
class AskBrainSemanticReviewSummary:
    citation_pairs: int
    supported_pairs: int
    citation_correctness: float
    missing_reviews: int
    extra_reviews: int
    mismatched_evidence: int
    review_complete: bool
    dataset_eligible: bool
    automatic_gate_passed: bool
    production_passed: bool


def evaluate_case(
    *,
    case_id: str,
    expected_status: str,
    actual_status: str,
    supporting_canonical_event_ids: Iterable[str],
    forbidden_canonical_event_ids: Iterable[str],
    retrieved_canonical_event_ids: Iterable[str],
    cited_canonical_event_ids: Iterable[str],
    unresolved_citations: int = 0,
) -> AskBrainCaseEvaluation:
    if expected_status not in _VALID_STATUSES:
        raise ValueError("expected_status must be answer or insufficient_evidence")
    if unresolved_citations < 0:
        raise ValueError("unresolved_citations cannot be negative")

    supporting = set(supporting_canonical_event_ids)
    forbidden = set(forbidden_canonical_event_ids)
    if supporting & forbidden:
        raise ValueError("supporting and forbidden evidence must not overlap")

    retrieved = set(retrieved_canonical_event_ids)
    cited = list(cited_canonical_event_ids)
    exposed_forbidden = (retrieved | set(cited)) & forbidden
    contract_failure = (
        actual_status not in _VALID_STATUSES
        or unresolved_citations > 0
        or (actual_status == "answer" and not cited)
    )

    return AskBrainCaseEvaluation(
        case_id=case_id,
        expected_status=expected_status,
        actual_status=actual_status,
        expected_relevant=len(supporting),
        retrieved_relevant=len(supporting & retrieved),
        citation_targets_total=len(cited),
        citation_targets_relevant=sum(1 for item in cited if item in supporting),
        unresolved_citations=unresolved_citations,
        forbidden_exposures=len(exposed_forbidden),
        status_matches=actual_status == expected_status,
        contract_failure=contract_failure,
        unsafe_answer=(
            expected_status == "insufficient_evidence" and actual_status == "answer"
        ),
    )


def summarize_evaluation(
    cases: Iterable[AskBrainCaseEvaluation],
    *,
    dataset_eligible: bool,
) -> AskBrainEvaluationSummary:
    rows = list(cases)
    if not rows:
        raise ValueError("evaluation requires at least one case")

    expected_relevant = sum(row.expected_relevant for row in rows)
    retrieved_relevant = sum(row.retrieved_relevant for row in rows)
    citation_targets_total = sum(row.citation_targets_total for row in rows)
    citation_targets_relevant = sum(row.citation_targets_relevant for row in rows)
    expected_answer_cases = sum(1 for row in rows if row.expected_status == "answer")

    retrieval_recall = (
        retrieved_relevant / expected_relevant if expected_relevant else 0.0
    )
    if citation_targets_total:
        citation_target_precision = citation_targets_relevant / citation_targets_total
    else:
        citation_target_precision = 0.0 if expected_answer_cases else 1.0
    status_accuracy = sum(row.status_matches for row in rows) / len(rows)
    forbidden_exposures = sum(row.forbidden_exposures for row in rows)
    contract_failures = sum(row.contract_failure for row in rows)
    unsafe_answers = sum(row.unsafe_answer for row in rows)

    automatic_gate_passed = (
        dataset_eligible
        and retrieval_recall >= RETRIEVAL_RECALL_TARGET
        and forbidden_exposures == 0
        and contract_failures == 0
        and unsafe_answers == 0
    )
    return AskBrainEvaluationSummary(
        cases=len(rows),
        retrieval_recall=retrieval_recall,
        citation_target_precision=citation_target_precision,
        status_accuracy=status_accuracy,
        forbidden_exposures=forbidden_exposures,
        contract_failures=contract_failures,
        unsafe_answers=unsafe_answers,
        dataset_eligible=dataset_eligible,
        automatic_gate_passed=automatic_gate_passed,
        semantic_review_required=True,
        production_passed=False,
    )


def _pair_key(
    case_id: str,
    claim_index: int,
    citation_index: int,
) -> tuple[str, int, int]:
    return case_id, claim_index, citation_index


def score_semantic_reviews(
    observed_pairs: Iterable[ObservedCitationPair],
    reviews: Iterable[CitationPairReview],
    *,
    dataset_eligible: bool,
    automatic_gate_passed: bool,
) -> AskBrainSemanticReviewSummary:
    observed_rows = list(observed_pairs)
    review_rows = list(reviews)

    observed: dict[tuple[str, int, int], ObservedCitationPair] = {}
    for row in observed_rows:
        key = _pair_key(row.case_id, row.claim_index, row.citation_index)
        if key in observed:
            raise ValueError("duplicate observed claim-citation pair")
        observed[key] = row

    reviewed: dict[tuple[str, int, int], CitationPairReview] = {}
    for row in review_rows:
        key = _pair_key(row.case_id, row.claim_index, row.citation_index)
        if key in reviewed:
            raise ValueError("duplicate human review claim-citation pair")
        reviewed[key] = row

    observed_keys = set(observed)
    review_keys = set(reviewed)
    missing_keys = observed_keys - review_keys
    extra_keys = review_keys - observed_keys
    shared_keys = observed_keys & review_keys
    mismatched = sum(
        1
        for key in shared_keys
        if observed[key].canonical_event_id != reviewed[key].canonical_event_id
    )
    supported = sum(
        1
        for key in shared_keys
        if observed[key].canonical_event_id == reviewed[key].canonical_event_id
        and reviewed[key].supported
    )
    correctness = supported / len(observed_rows) if observed_rows else 0.0
    complete = not missing_keys and not extra_keys and mismatched == 0
    production_passed = (
        dataset_eligible
        and automatic_gate_passed
        and complete
        and bool(observed_rows)
        and correctness >= CITATION_CORRECTNESS_TARGET
    )

    return AskBrainSemanticReviewSummary(
        citation_pairs=len(observed_rows),
        supported_pairs=supported,
        citation_correctness=correctness,
        missing_reviews=len(missing_keys),
        extra_reviews=len(extra_keys),
        mismatched_evidence=mismatched,
        review_complete=complete,
        dataset_eligible=dataset_eligible,
        automatic_gate_passed=automatic_gate_passed,
        production_passed=production_passed,
    )
