from app.ask_brain_evaluation import evaluate_case, summarize_evaluation


def test_evaluation_enforces_retrieval_and_citation_targets() -> None:
    supporting = [f"event-{index}" for index in range(10)]
    case = evaluate_case(
        case_id="thresholds",
        expected_status="answer",
        actual_status="answer",
        supporting_canonical_event_ids=supporting,
        forbidden_canonical_event_ids=[],
        retrieved_canonical_event_ids=supporting[:9],
        cited_canonical_event_ids=[supporting[0]] * 98 + ["wrong-a", "wrong-b"],
    )

    summary = summarize_evaluation([case], eligible_for_production_claim=True)

    assert summary.retrieval_recall == 0.90
    assert summary.citation_correctness == 0.98
    assert summary.passed


def test_evaluation_fails_below_explicit_product_gate() -> None:
    case = evaluate_case(
        case_id="below-gate",
        expected_status="answer",
        actual_status="answer",
        supporting_canonical_event_ids=["event-a", "event-b"],
        forbidden_canonical_event_ids=[],
        retrieved_canonical_event_ids=["event-a"],
        cited_canonical_event_ids=["event-a", "wrong"],
    )

    summary = summarize_evaluation([case], eligible_for_production_claim=True)

    assert summary.retrieval_recall == 0.5
    assert summary.citation_correctness == 0.5
    assert not summary.passed


def test_evaluation_fails_on_forbidden_evidence_even_when_scores_are_high() -> None:
    case = evaluate_case(
        case_id="leakage",
        expected_status="answer",
        actual_status="answer",
        supporting_canonical_event_ids=["event-a"],
        forbidden_canonical_event_ids=["secret-event"],
        retrieved_canonical_event_ids=["event-a", "secret-event"],
        cited_canonical_event_ids=["event-a"],
    )

    summary = summarize_evaluation([case], eligible_for_production_claim=True)

    assert summary.forbidden_exposures == 1
    assert not summary.passed


def test_example_or_unreviewed_dataset_cannot_become_production_evidence() -> None:
    case = evaluate_case(
        case_id="synthetic",
        expected_status="answer",
        actual_status="answer",
        supporting_canonical_event_ids=["event-a"],
        forbidden_canonical_event_ids=[],
        retrieved_canonical_event_ids=["event-a"],
        cited_canonical_event_ids=["event-a"],
    )

    summary = summarize_evaluation([case], eligible_for_production_claim=False)

    assert summary.retrieval_recall == 1.0
    assert summary.citation_correctness == 1.0
    assert not summary.passed


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

    summary = summarize_evaluation([case], eligible_for_production_claim=True)

    assert summary.unsafe_answers == 1
    assert not summary.passed
