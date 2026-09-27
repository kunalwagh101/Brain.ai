import uuid

import pytest
from pydantic import ValidationError

from app.ask_brain import (
    DEFAULT_ASK_BRAIN_OUTPUT_TOKENS,
    MAX_ASK_BRAIN_OUTPUT_TOKENS,
    AskBrainError,
    _effective_max_output_tokens,
)
from app.routes.ask_brain import AskBrainRequest


def _request(**overrides):
    values = {
        "question": "What changed?",
        "provider_configuration_id": uuid.uuid4(),
        "model_configuration_id": uuid.uuid4(),
    }
    values.update(overrides)
    return AskBrainRequest(**values)


def test_ask_brain_has_bounded_default_output_tokens() -> None:
    payload = _request()

    assert payload.max_output_tokens == DEFAULT_ASK_BRAIN_OUTPUT_TOKENS
    assert payload.max_output_tokens == MAX_ASK_BRAIN_OUTPUT_TOKENS


def test_route_rejects_excessive_output_token_request() -> None:
    with pytest.raises(ValidationError):
        _request(max_output_tokens=MAX_ASK_BRAIN_OUTPUT_TOKENS + 1)


def test_service_defensively_rejects_excessive_output_token_request() -> None:
    with pytest.raises(AskBrainError, match="max_output_tokens_invalid"):
        _effective_max_output_tokens(MAX_ASK_BRAIN_OUTPUT_TOKENS + 1)


def test_service_uses_safe_default_when_internal_caller_omits_limit() -> None:
    assert _effective_max_output_tokens(None) == DEFAULT_ASK_BRAIN_OUTPUT_TOKENS
