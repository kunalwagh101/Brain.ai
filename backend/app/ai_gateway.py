import ipaddress
import json
import re
import socket
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.ai_gateway_models import (
    AIModelConfiguration,
    AIProviderAdapterKind,
    AIProviderConfiguration,
    AIProviderStatus,
    AIRequestRecord,
    AIRequestStatus,
)
from app.config import Settings, get_settings
from app.models import MembershipRole
from app.secrets import SecretStore, SecretStoreError
from app.work_graph import node_visible_to_user
from app.work_graph_models import WorkGraphNode, WorkGraphNodeType

_PROVIDER_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_MODEL_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,254}$")


class AIGatewayError(ValueError):
    pass


class AIProviderCallError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code[:128]


class AIInvocationError(RuntimeError):
    def __init__(self, *, request_id: uuid.UUID, code: str) -> None:
        super().__init__(code)
        self.request_id = request_id
        self.code = code[:128]


@dataclass(frozen=True, slots=True)
class AIProviderResult:
    output_text: str
    provider_request_id: str | None
    input_tokens: int | None
    output_tokens: int | None


@dataclass(frozen=True, slots=True)
class AIInvocationResult:
    request_id: uuid.UUID
    output_text: str
    provider_request_id: str | None
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int


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
            with urlopen(request, timeout=timeout_seconds) as response:
                raw = response.read()
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
    if production:
        if parsed.scheme != "https":
            raise AIGatewayError("Production AI provider URLs must use HTTPS")
        if host not in settings.allowed_ai_provider_hosts:
            raise AIGatewayError("AI provider host is not approved for production egress")
    elif parsed.scheme == "http" and host not in {"localhost", "127.0.0.1", "::1"}:
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


def create_provider_configuration(
    db: Session,
    *,
    secret_store: SecretStore,
    organization_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    provider_key: str,
    display_name: str,
    adapter_kind: AIProviderAdapterKind,
    api_url: str,
    credentials: dict[str, str],
) -> AIProviderConfiguration:
    provider_key = normalize_provider_key(provider_key)
    api_url = validate_provider_api_url(api_url)
    if not display_name.strip():
        raise AIGatewayError("Provider display name is required")
    api_key = credentials.get("api_key")
    if not isinstance(api_key, str) or not api_key.strip():
        raise AIGatewayError("AI provider credentials require api_key")

    duplicate = db.scalar(
        select(AIProviderConfiguration.id).where(
            AIProviderConfiguration.organization_id == organization_id,
            AIProviderConfiguration.provider_key == provider_key,
        )
    )
    if duplicate is not None:
        raise AIGatewayError("AI provider configuration already exists")

    provider_id = uuid.uuid4()
    try:
        secret_ref = secret_store.store_ai_provider_secret(
            organization_id=organization_id,
            provider_configuration_id=provider_id,
            provider=provider_key,
            credentials=credentials,
        )
    except SecretStoreError as exc:
        raise AIGatewayError("AI provider credential storage failed") from exc

    provider = AIProviderConfiguration(
        id=provider_id,
        organization_id=organization_id,
        provider_key=provider_key,
        display_name=display_name.strip(),
        adapter_kind=adapter_kind,
        api_url=api_url,
        secret_ref=secret_ref,
        status=AIProviderStatus.ENABLED,
        created_by_user_id=actor_user_id,
    )
    db.add(provider)
    try:
        db.commit()
    except (IntegrityError, SQLAlchemyError) as exc:
        db.rollback()
        try:
            secret_store.schedule_delete(secret_ref)
        except SecretStoreError:
            pass
        raise AIGatewayError("AI provider configuration could not be persisted") from exc
    db.refresh(provider)
    return provider


def create_model_configuration(
    db: Session,
    *,
    organization_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    provider_configuration_id: uuid.UUID,
    model_key: str,
    display_name: str,
    enabled: bool,
    max_output_tokens: int | None,
) -> AIModelConfiguration:
    provider = db.scalar(
        select(AIProviderConfiguration).where(
            AIProviderConfiguration.id == provider_configuration_id,
            AIProviderConfiguration.organization_id == organization_id,
        )
    )
    if provider is None:
        raise AIGatewayError("AI provider configuration not found")
    if provider.status == AIProviderStatus.REVOKED:
        raise AIGatewayError("AI provider configuration is revoked")
    model_key = normalize_model_key(model_key)
    if not display_name.strip():
        raise AIGatewayError("Model display name is required")
    if max_output_tokens is not None and not 1 <= max_output_tokens <= 1_000_000:
        raise AIGatewayError("max_output_tokens is outside the supported range")

    duplicate = db.scalar(
        select(AIModelConfiguration.id).where(
            AIModelConfiguration.provider_configuration_id == provider.id,
            AIModelConfiguration.model_key == model_key,
        )
    )
    if duplicate is not None:
        raise AIGatewayError("AI model configuration already exists")
    model = AIModelConfiguration(
        organization_id=organization_id,
        provider_configuration_id=provider.id,
        model_key=model_key,
        display_name=display_name.strip(),
        enabled=enabled,
        max_output_tokens=max_output_tokens,
        created_by_user_id=actor_user_id,
    )
    db.add(model)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AIGatewayError("AI model configuration already exists") from exc
    db.refresh(model)
    return model


def set_provider_enabled(
    db: Session,
    *,
    organization_id: uuid.UUID,
    provider_configuration_id: uuid.UUID,
    enabled: bool,
) -> AIProviderConfiguration:
    provider = db.scalar(
        select(AIProviderConfiguration).where(
            AIProviderConfiguration.id == provider_configuration_id,
            AIProviderConfiguration.organization_id == organization_id,
        )
    )
    if provider is None:
        raise AIGatewayError("AI provider configuration not found")
    if provider.status == AIProviderStatus.REVOKED:
        raise AIGatewayError("AI provider configuration is revoked")
    provider.status = AIProviderStatus.ENABLED if enabled else AIProviderStatus.DISABLED
    db.commit()
    db.refresh(provider)
    return provider


def set_model_enabled(
    db: Session,
    *,
    organization_id: uuid.UUID,
    model_configuration_id: uuid.UUID,
    enabled: bool,
) -> AIModelConfiguration:
    model = db.scalar(
        select(AIModelConfiguration).where(
            AIModelConfiguration.id == model_configuration_id,
            AIModelConfiguration.organization_id == organization_id,
        )
    )
    if model is None:
        raise AIGatewayError("AI model configuration not found")
    model.enabled = enabled
    db.commit()
    db.refresh(model)
    return model


def revoke_provider_configuration(
    db: Session,
    *,
    secret_store: SecretStore,
    organization_id: uuid.UUID,
    provider_configuration_id: uuid.UUID,
) -> AIProviderConfiguration:
    provider = db.scalar(
        select(AIProviderConfiguration).where(
            AIProviderConfiguration.id == provider_configuration_id,
            AIProviderConfiguration.organization_id == organization_id,
        )
    )
    if provider is None:
        raise AIGatewayError("AI provider configuration not found")
    if provider.status == AIProviderStatus.REVOKED:
        return provider

    provider.status = AIProviderStatus.DISABLED
    db.commit()
    reference = provider.secret_ref
    if reference:
        try:
            secret_store.schedule_delete(reference)
        except SecretStoreError as exc:
            raise AIGatewayError("AI provider revocation is incomplete") from exc
    provider.status = AIProviderStatus.REVOKED
    provider.secret_ref = None
    provider.revoked_at = datetime.now(UTC)
    db.commit()
    db.refresh(provider)
    return provider


def _validate_attribution(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    role: MembershipRole,
    attribution_node_id: uuid.UUID | None,
) -> tuple[uuid.UUID | None, str | None]:
    if attribution_node_id is None:
        return None, None
    node = db.scalar(
        select(WorkGraphNode).where(
            WorkGraphNode.id == attribution_node_id,
            WorkGraphNode.organization_id == organization_id,
        )
    )
    if node is None or node.node_type not in {
        WorkGraphNodeType.PROJECT,
        WorkGraphNodeType.WORK_ITEM,
    }:
        raise AIGatewayError("AI request attribution resource not found")
    if not node_visible_to_user(db, node, user_id=user_id, role=role):
        raise AIGatewayError("AI request attribution resource not found")
    return node.id, node.node_type.value


def _mark_failed(
    db: Session,
    record: AIRequestRecord,
    *,
    code: str,
    started: float,
) -> None:
    record.status = AIRequestStatus.FAILED
    record.error_code = code[:128]
    record.latency_ms = max(0, round((time.perf_counter() - started) * 1000))
    record.completed_at = datetime.now(UTC)
    db.commit()


def invoke_ai(
    db: Session,
    *,
    secret_store: SecretStore,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    role: MembershipRole,
    provider_configuration_id: uuid.UUID,
    model_configuration_id: uuid.UUID,
    input_text: str,
    system_text: str | None,
    max_output_tokens: int | None,
    attribution_node_id: uuid.UUID | None,
    adapter: AIProviderAdapter | None = None,
    timeout_seconds: float | None = None,
) -> AIInvocationResult:
    provider = db.scalar(
        select(AIProviderConfiguration).where(
            AIProviderConfiguration.id == provider_configuration_id,
            AIProviderConfiguration.organization_id == organization_id,
        )
    )
    model = db.scalar(
        select(AIModelConfiguration).where(
            AIModelConfiguration.id == model_configuration_id,
            AIModelConfiguration.organization_id == organization_id,
            AIModelConfiguration.provider_configuration_id == provider_configuration_id,
        )
    )
    if provider is None or model is None:
        raise AIGatewayError("AI provider or model not found")
    if provider.status != AIProviderStatus.ENABLED or not model.enabled:
        raise AIGatewayError("AI provider or model is disabled")
    text = input_text.strip()
    if not text:
        raise AIGatewayError("AI input is required")
    if len(text) > 200_000:
        raise AIGatewayError("AI input exceeds the gateway limit")
    normalized_system = system_text.strip() if system_text else None
    if normalized_system and len(normalized_system) > 50_000:
        raise AIGatewayError("AI system input exceeds the gateway limit")

    node_id, node_type = _validate_attribution(
        db,
        organization_id=organization_id,
        user_id=user_id,
        role=role,
        attribution_node_id=attribution_node_id,
    )
    effective_max = max_output_tokens or model.max_output_tokens
    if effective_max is not None and not 1 <= effective_max <= 1_000_000:
        raise AIGatewayError("max_output_tokens is outside the supported range")

    record = AIRequestRecord(
        organization_id=organization_id,
        user_id=user_id,
        provider_configuration_id=provider.id,
        model_configuration_id=model.id,
        provider_key=provider.provider_key,
        model_key=model.model_key,
        attribution_node_id=node_id,
        attribution_node_type=node_type,
        status=AIRequestStatus.PENDING,
        input_char_count=len(text) + (len(normalized_system) if normalized_system else 0),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    started = time.perf_counter()

    if not provider.secret_ref:
        _mark_failed(db, record, code="provider_revoked", started=started)
        raise AIInvocationError(request_id=record.id, code="provider_revoked")
    try:
        credentials = secret_store.load_connection_secret(provider.secret_ref)
    except SecretStoreError as exc:
        _mark_failed(db, record, code="credential_unavailable", started=started)
        raise AIInvocationError(
            request_id=record.id,
            code="credential_unavailable",
        ) from exc
    api_key = credentials.get("api_key")
    if not isinstance(api_key, str) or not api_key:
        _mark_failed(db, record, code="invalid_provider_credentials", started=started)
        raise AIInvocationError(
            request_id=record.id,
            code="invalid_provider_credentials",
        )

    runtime = adapter or adapter_for(provider.adapter_kind)
    timeout = timeout_seconds or get_settings().ai_provider_timeout_seconds
    try:
        result = runtime.invoke(
            api_url=provider.api_url,
            api_key=api_key,
            model=model.model_key,
            input_text=text,
            system_text=normalized_system,
            max_output_tokens=effective_max,
            timeout_seconds=timeout,
        )
    except AIProviderCallError as exc:
        _mark_failed(db, record, code=exc.code, started=started)
        raise AIInvocationError(request_id=record.id, code=exc.code) from exc

    latency_ms = max(0, round((time.perf_counter() - started) * 1000))
    record.status = AIRequestStatus.SUCCEEDED
    record.output_char_count = len(result.output_text)
    record.input_tokens = result.input_tokens
    record.output_tokens = result.output_tokens
    record.latency_ms = latency_ms
    record.provider_request_id = result.provider_request_id
    record.error_code = None
    record.completed_at = datetime.now(UTC)
    db.commit()
    return AIInvocationResult(
        request_id=record.id,
        output_text=result.output_text,
        provider_request_id=result.provider_request_id,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        latency_ms=latency_ms,
    )
