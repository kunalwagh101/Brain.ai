import ipaddress
import json
import re
import socket
from dataclasses import dataclass
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from app.ai_gateway_models import AIProviderAdapterKind
from app.config import Settings, get_settings

_PROVIDER_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_MODEL_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,254}$")
_MAX_PROVIDER_RESPONSE_BYTES = 4_000_000


class AIGatewayError(ValueError):
    """Raised when AI gateway configuration or invocation input is invalid."""


class AIProviderCallError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code[:128]


@dataclass(frozen=True, slots=True)
class AIProviderResult:
    output_text: str
    provider_request_id: str | None
    input_tokens: int | None
    output_tokens: int | None
    cached_input_tokens: int | None = None


class AIProviderAdapter(Protocol):
    def invoke(
        self,
        *,
        api_url: str,
        api_key: str,
        model: str,
        input_text: str,
        system_text: str | None,
        max_output_tokens: int | None,
        timeout_seconds: float,
    ) -> AIProviderResult: ...


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(
        self,
        req,
        fp,
        code,
        msg,
        headers,
        newurl,
    ):
        del req, fp, code, msg, headers, newurl
        return None


def _open_provider_request(request: Request, timeout_seconds: float):
    opener = build_opener(_NoRedirectHandler())
    return opener.open(request, timeout=timeout_seconds)


def _int_or_none(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return max(0, value)


class OpenAIChatCompletionsAdapter:
    def invoke(
        self,
        *,
        api_url: str,
        api_key: str,
        model: str,
        input_text: str,
        system_text: str | None,
        max_output_tokens: int | None,
        timeout_seconds: float,
    ) -> AIProviderResult:
        messages: list[dict[str, str]] = []
        if system_text:
            messages.append({"role": "system", "content": system_text})
        messages.append({"role": "user", "content": input_text})
        payload: dict[str, object] = {"model": model, "messages": messages}
        if max_output_tokens is not None:
            payload["max_tokens"] = max_output_tokens
        request = Request(
            api_url,
            data=json.dumps(payload, separators=(",", ":")).encode(),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with _open_provider_request(request, timeout_seconds) as response:
                raw = response.read(_MAX_PROVIDER_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            if exc.code == 429:
                raise AIProviderCallError("rate_limited") from exc
            if exc.code in {401, 403}:
                raise AIProviderCallError("provider_auth_failed") from exc
            if 400 <= exc.code < 500:
                raise AIProviderCallError("provider_rejected_request") from exc
            raise AIProviderCallError("provider_unavailable") from exc
        except (TimeoutError, socket.timeout) as exc:
            raise AIProviderCallError("provider_timeout") from exc
        except URLError as exc:
            raise AIProviderCallError("provider_unavailable") from exc

        if len(raw) > _MAX_PROVIDER_RESPONSE_BYTES:
            raise AIProviderCallError("provider_response_too_large")
        try:
            data = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AIProviderCallError("malformed_provider_response") from exc
        if not isinstance(data, dict):
            raise AIProviderCallError("malformed_provider_response")
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise AIProviderCallError("malformed_provider_response")
        first = choices[0]
        if not isinstance(first, dict):
            raise AIProviderCallError("malformed_provider_response")
        message = first.get("message")
        if not isinstance(message, dict):
            raise AIProviderCallError("malformed_provider_response")
        content = message.get("content")
        if not isinstance(content, str):
            raise AIProviderCallError("malformed_provider_response")

        usage = data.get("usage")
        usage_dict = usage if isinstance(usage, dict) else {}
        prompt_details = usage_dict.get("prompt_tokens_details")
        prompt_details_dict = prompt_details if isinstance(prompt_details, dict) else {}
        provider_request_id = data.get("id")
        return AIProviderResult(
            output_text=content,
            provider_request_id=(
                provider_request_id[:255]
                if isinstance(provider_request_id, str)
                else None
            ),
            input_tokens=_int_or_none(usage_dict.get("prompt_tokens")),
            output_tokens=_int_or_none(usage_dict.get("completion_tokens")),
            cached_input_tokens=_int_or_none(prompt_details_dict.get("cached_tokens")),
        )


def adapter_for(kind: AIProviderAdapterKind) -> AIProviderAdapter:
    if kind == AIProviderAdapterKind.OPENAI_CHAT_COMPLETIONS:
        return OpenAIChatCompletionsAdapter()
    raise AIGatewayError("Unsupported AI provider adapter")


def validate_provider_api_url(url: str, *, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    normalized = url.strip()
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise AIGatewayError("AI provider URL must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password or parsed.fragment:
        raise AIGatewayError("AI provider URL contains unsupported credentials or fragment")

    host = parsed.hostname.lower()
    production = settings.environment.lower() == "production"
    if production and parsed.scheme != "https":
        raise AIGatewayError("Production AI provider URLs must use HTTPS")
    if production and host not in settings.allowed_ai_provider_hosts:
        raise AIGatewayError("AI provider host is not approved for production egress")
    if not production and parsed.scheme == "http" and host not in {
        "localhost",
        "127.0.0.1",
        "::1",
    }:
        raise AIGatewayError("Non-local AI provider URLs must use HTTPS")

    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and production and (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_unspecified
    ):
        raise AIGatewayError("Private or special-address AI egress is not allowed")
    return normalized


def normalize_provider_key(value: str) -> str:
    key = value.strip().lower()
    if not _PROVIDER_KEY_RE.fullmatch(key):
        raise AIGatewayError("Provider key contains unsupported characters")
    return key


def normalize_model_key(value: str) -> str:
    key = value.strip()
    if not _MODEL_KEY_RE.fullmatch(key):
        raise AIGatewayError("Model key contains unsupported characters")
    return key
