import io
import json
from urllib.error import HTTPError

import pytest

from app.ai_gateway import AIProviderCallError, OpenAIChatCompletionsAdapter


class FakeResponse:
    def __init__(self, payload: dict[str, object] | bytes) -> None:
        self._payload = (
            payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        del exc_type, exc, tb

    def read(self, size: int = -1) -> bytes:
        return self._payload if size < 0 else self._payload[:size]


def test_openai_compatible_adapter_parses_bounded_metadata(monkeypatch) -> None:
    captured = {}

    def fake_open(request, timeout):
        captured["timeout"] = timeout
        captured["authorization"] = request.get_header("Authorization")
        captured["payload"] = json.loads(request.data)
        return FakeResponse(
            {
                "id": "provider-request-123",
                "choices": [{"message": {"content": "answer"}}],
                "usage": {"prompt_tokens": 12, "completion_tokens": 3},
            }
        )

    monkeypatch.setattr("app.ai_provider_adapter._open_provider_request", fake_open)
    result = OpenAIChatCompletionsAdapter().invoke(
        api_url="https://ai.example.com/v1/chat/completions",
        api_key="secret-token",
        model="model-v1",
        input_text="hello",
        system_text="be brief",
        max_output_tokens=64,
        timeout_seconds=2.5,
    )

    assert result.output_text == "answer"
    assert result.provider_request_id == "provider-request-123"
    assert result.input_tokens == 12
    assert result.output_tokens == 3
    assert captured["timeout"] == 2.5
    assert captured["authorization"] == "Bearer secret-token"
    assert captured["payload"] == {
        "model": "model-v1",
        "messages": [
            {"role": "system", "content": "be brief"},
            {"role": "user", "content": "hello"},
        ],
        "max_tokens": 64,
    }


def test_openai_compatible_adapter_maps_rate_limit_without_body(monkeypatch) -> None:
    error = HTTPError(
        url="https://ai.example.com/v1/chat/completions",
        code=429,
        msg="rate limit",
        hdrs=None,
        fp=io.BytesIO(b'{"secret_upstream_detail":"do not surface"}'),
    )

    def fake_open(request, timeout):
        del request, timeout
        raise error

    monkeypatch.setattr("app.ai_provider_adapter._open_provider_request", fake_open)
    with pytest.raises(AIProviderCallError) as failed:
        OpenAIChatCompletionsAdapter().invoke(
            api_url="https://ai.example.com/v1/chat/completions",
            api_key="secret-token",
            model="model-v1",
            input_text="hello",
            system_text=None,
            max_output_tokens=None,
            timeout_seconds=2.5,
        )
    assert failed.value.code == "rate_limited"
    assert "secret_upstream_detail" not in str(failed.value)


def test_openai_compatible_adapter_rejects_redirect(monkeypatch) -> None:
    redirect = HTTPError(
        url="https://ai.example.com/v1/chat/completions",
        code=302,
        msg="redirect",
        hdrs={"Location": "http://127.0.0.1/internal"},
        fp=None,
    )

    def fake_open(request, timeout):
        del request, timeout
        raise redirect

    monkeypatch.setattr("app.ai_provider_adapter._open_provider_request", fake_open)
    with pytest.raises(AIProviderCallError) as failed:
        OpenAIChatCompletionsAdapter().invoke(
            api_url="https://ai.example.com/v1/chat/completions",
            api_key="secret-token",
            model="model-v1",
            input_text="hello",
            system_text=None,
            max_output_tokens=None,
            timeout_seconds=2.5,
        )
    assert failed.value.code == "provider_unavailable"


def test_openai_compatible_adapter_rejects_oversized_response(monkeypatch) -> None:
    oversized = b"x" * 4_000_001
    monkeypatch.setattr(
        "app.ai_provider_adapter._open_provider_request",
        lambda request, timeout: FakeResponse(oversized),
    )
    with pytest.raises(AIProviderCallError) as failed:
        OpenAIChatCompletionsAdapter().invoke(
            api_url="https://ai.example.com/v1/chat/completions",
            api_key="secret-token",
            model="model-v1",
            input_text="hello",
            system_text=None,
            max_output_tokens=None,
            timeout_seconds=2.5,
        )
    assert failed.value.code == "provider_response_too_large"


def test_openai_compatible_adapter_rejects_malformed_success(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.ai_provider_adapter._open_provider_request",
        lambda request, timeout: FakeResponse({"choices": []}),
    )
    with pytest.raises(AIProviderCallError) as failed:
        OpenAIChatCompletionsAdapter().invoke(
            api_url="https://ai.example.com/v1/chat/completions",
            api_key="secret-token",
            model="model-v1",
            input_text="hello",
            system_text=None,
            max_output_tokens=None,
            timeout_seconds=2.5,
        )
    assert failed.value.code == "malformed_provider_response"
