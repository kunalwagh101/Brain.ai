import uuid

import pytest

from app.ask_brain import AskBrainError, _parse_model_output


def test_model_output_rejects_unexpected_top_level_fields() -> None:
    request_id = uuid.uuid4()
    output = (
        '{"status":"answer","claims":[{"text":"Atlas ships Friday.",'
        '"citations":["E1"]}],"uncertainty":null,"instructions":"ignore policy"}'
    )

    with pytest.raises(AskBrainError) as exc_info:
        _parse_model_output(
            output,
            available_citations={"E1": object()},  # type: ignore[dict-item]
            request_id=request_id,
        )

    assert exc_info.value.code == "invalid_model_output"
    assert exc_info.value.request_id == request_id


def test_model_output_rejects_unexpected_claim_fields() -> None:
    request_id = uuid.uuid4()
    output = (
        '{"status":"answer","claims":[{"text":"Atlas ships Friday.",'
        '"citations":["E1"],"confidence":1}],"uncertainty":null}'
    )

    with pytest.raises(AskBrainError) as exc_info:
        _parse_model_output(
            output,
            available_citations={"E1": object()},  # type: ignore[dict-item]
            request_id=request_id,
        )

    assert exc_info.value.code == "invalid_model_output"
    assert exc_info.value.request_id == request_id


def test_model_output_accepts_exact_grounded_contract() -> None:
    request_id = uuid.uuid4()
    status, claims, uncertainty = _parse_model_output(
        '{"status":"answer","claims":[{"text":"Atlas ships Friday.",'
        '"citations":["E1"]}],"uncertainty":null}',
        available_citations={"E1": object()},  # type: ignore[dict-item]
        request_id=request_id,
    )

    assert status == "answer"
    assert claims[0].text == "Atlas ships Friday."
    assert claims[0].citation_ids == ("E1",)
    assert uncertainty is None
