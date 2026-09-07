import logging
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

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
from app.ai_provider_adapter import (
    AIGatewayError,
    AIProviderAdapter,
    AIProviderCallError,
    adapter_for,
    normalize_model_key,
    normalize_provider_key,
    validate_provider_api_url,
)
from app.ai_usage import exhausted_hard_budget, materialize_request_cost
from app.ai_usage_models import AICostResolutionStatus
from app.config import get_settings
from app.models import MembershipRole
from app.observability import get_tracer, log_event, record_ai_request
from app.secrets import SecretStore, SecretStoreError
from app.work_graph import node_visible_to_user
from app.work_graph_models import WorkGraphNode, WorkGraphNodeType

logger = logging.getLogger("brain.ai")


class AIInvocationError(RuntimeError):
    def __init__(self, *, request_id: uuid.UUID, code: str) -> None:
        super().__init__(code)
        self.request_id = request_id
        self.code = code[:128]


@dataclass(frozen=True, slots=True)
class AIInvocationResult:
    request_id: uuid.UUID
    output_text: str
    provider_request_id: str | None
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int


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
    except SQLAlchemyError as exc:
        db.rollback()
        try:
            secret_store.schedule_delete(secret_ref)
        except SecretStoreError:
            logger.exception("Failed to clean up orphaned AI provider secret")
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
    if provider.status not in {
        AIProviderStatus.ENABLED,
        AIProviderStatus.DISABLED,
    }:
        raise AIGatewayError("AI provider revocation has started")
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
    if provider.status not in {
        AIProviderStatus.ENABLED,
        AIProviderStatus.DISABLED,
    }:
        raise AIGatewayError("AI provider cannot be re-enabled after revocation starts")
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

    provider.status = AIProviderStatus.REVOKING
    db.commit()
    reference = provider.secret_ref
    if reference:
        try:
            secret_store.schedule_delete(reference)
        except SecretStoreError as exc:
            provider.status = AIProviderStatus.REVOKE_FAILED
            db.commit()
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
        WorkGraphNodeType.TRACK,
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
    organization_id: uuid.UUID,
    provider: str,
    model: str,
) -> None:
    latency_ms = max(0, round((time.perf_counter() - started) * 1000))
    record.status = AIRequestStatus.FAILED
    record.error_code = code[:128]
    record.latency_ms = latency_ms
    record.completed_at = datetime.now(UTC)
    db.commit()
    record_ai_request(
        provider=provider,
        model=model,
        status_value="failed",
        latency_ms=latency_ms,
    )
    log_event(
        logger,
        logging.ERROR,
        "ai.request.failed",
        organization_id=organization_id,
        provider=provider,
        model=model,
        error_code=code[:128],
        duration_ms=latency_ms,
    )


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
    validate_provider_api_url(provider.api_url)
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

    exhausted = exhausted_hard_budget(
        db,
        organization_id=organization_id,
        provider_configuration_id=provider.id,
        model_configuration_id=model.id,
        user_id=user_id,
        attribution_node_id=node_id,
        at=datetime.now(UTC),
    )
    if exhausted is not None:
        raise AIGatewayError("AI budget exhausted")

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
    tracer = get_tracer("brain.ai")

    with tracer.start_as_current_span("ai.provider.invoke") as span:
        span.set_attribute("brain.organization_id", str(organization_id))
        span.set_attribute("brain.ai_request_id", str(record.id))
        span.set_attribute("brain.provider", provider.provider_key)
        span.set_attribute("brain.model", model.model_key)

        failure_fields = {
            "organization_id": organization_id,
            "provider": provider.provider_key,
            "model": model.model_key,
        }
        if not provider.secret_ref:
            _mark_failed(
                db,
                record,
                code="provider_revoked",
                started=started,
                **failure_fields,
            )
            raise AIInvocationError(request_id=record.id, code="provider_revoked")
        try:
            credentials = secret_store.load_connection_secret(provider.secret_ref)
        except SecretStoreError as exc:
            _mark_failed(
                db,
                record,
                code="credential_unavailable",
                started=started,
                **failure_fields,
            )
            raise AIInvocationError(
                request_id=record.id,
                code="credential_unavailable",
            ) from exc
        api_key = credentials.get("api_key")
        if not isinstance(api_key, str) or not api_key:
            _mark_failed(
                db,
                record,
                code="invalid_provider_credentials",
                started=started,
                **failure_fields,
            )
            raise AIInvocationError(
                request_id=record.id,
                code="invalid_provider_credentials",
            )

        runtime = adapter or adapter_for(provider.adapter_kind)
        timeout = timeout_seconds or get_settings().ai_provider_timeout_seconds
        if timeout <= 0 or timeout > 120:
            _mark_failed(
                db,
                record,
                code="invalid_gateway_timeout",
                started=started,
                **failure_fields,
            )
            raise AIInvocationError(
                request_id=record.id,
                code="invalid_gateway_timeout",
            )
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
            _mark_failed(
                db,
                record,
                code=exc.code,
                started=started,
                **failure_fields,
            )
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

        resolved_cost: int | None = None
        try:
            cost = materialize_request_cost(db, request=record)
            if cost.status == AICostResolutionStatus.CALCULATED:
                resolved_cost = cost.total_cost_nano_usd
        except SQLAlchemyError:
            db.rollback()
            logger.exception("AI cost materialization failed request_id=%s", record.id)

        record_ai_request(
            provider=provider.provider_key,
            model=model.model_key,
            status_value="succeeded",
            latency_ms=latency_ms,
            cost_nano_usd=resolved_cost,
        )
        log_event(
            logger,
            logging.INFO,
            "ai.request.succeeded",
            organization_id=organization_id,
            provider=provider.provider_key,
            model=model.model_key,
            duration_ms=latency_ms,
            cost_nano_usd=resolved_cost,
        )
        span.set_attribute("brain.latency_ms", latency_ms)
        if resolved_cost is not None:
            span.set_attribute("brain.cost_nano_usd", resolved_cost)

        return AIInvocationResult(
            request_id=record.id,
            output_text=result.output_text,
            provider_request_id=result.provider_request_id,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            latency_ms=latency_ms,
        )
