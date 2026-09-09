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
    citations_total: int
    citations_correct: int
    unresolved_citations: int
    forbidden_exposures: int
    status_matches: bool
    contract_failure: bool
    unsafe_answer: bool


@dataclass(frozen=True, slots=True)
class AskBrainEvaluationSummary:
    cases: int
    retrieval_recall: float
    citation_correctness: float
    status_accuracy: float
    forbidden_exposures: int
    contract_failures: int
    unsafe_answers: int
    eligible_for_production_claim: bool
    passed: bool


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
        citations_total=len(cited),
        citations_correct=sum(1 for item in cited if item in supporting),
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
    eligible_for_production_claim: bool,
) -> AskBrainEvaluationSummary:
    rows = list(cases)
    if not rows:
        raise ValueError("evaluation requires at least one case")

    expected_relevant = sum(row.expected_relevant for row in rows)
    retrieved_relevant = sum(row.retrieved_relevant for row in rows)
    citations_total = sum(row.citations_total for row in rows)
    citations_correct = sum(row.citations_correct for row in rows)
    expected_answer_cases = sum(1 for row in rows if row.expected_status == "answer")

    retrieval_recall = (
        retrieved_relevant / expected_relevant if expected_relevant else 0.0
    )
    if citations_total:
        citation_correctness = citations_correct / citations_total
    else:
        citation_correctness = 0.0 if expected_answer_cases else 1.0
    status_accuracy = sum(row.status_matches for row in rows) / len(rows)
    forbidden_exposures = sum(row.forbidden_exposures for row in rows)
    contract_failures = sum(row.contract_failure for row in rows)
    unsafe_answers = sum(row.unsafe_answer for row in rows)

    passed = (
        eligible_for_production_claim
        and retrieval_recall >= RETRIEVAL_RECALL_TARGET
        and citation_correctness >= CITATION_CORRECTNESS_TARGET
        and forbidden_exposures == 0
        and contract_failures == 0
        and unsafe_answers == 0
    )
    return AskBrainEvaluationSummary(
        cases=len(rows),
        retrieval_recall=retrieval_recall,
        citation_correctness=citation_correctness,
        status_accuracy=status_accuracy,
        forbidden_exposures=forbidden_exposures,
        contract_failures=contract_failures,
        unsafe_answers=unsafe_answers,
        eligible_for_production_claim=eligible_for_production_claim,
        passed=passed,
    )
