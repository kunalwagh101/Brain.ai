import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class AIProviderStatus(StrEnum):
    ENABLED = "enabled"
    DISABLED = "disabled"
    REVOKING = "revoking"
    REVOKE_FAILED = "revoke_failed"
    REVOKED = "revoked"


class AIRequestStatus(StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class AIProviderAdapterKind(StrEnum):
    OPENAI_CHAT_COMPLETIONS = "openai_chat_completions"


class AIProviderConfiguration(Base):
    __tablename__ = "ai_provider_configurations"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "provider_key",
            name="uq_ai_provider_org_key",
        ),
        Index(
            "ix_ai_provider_org_status",
            "organization_id",
            "status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    provider_key: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    adapter_kind: Mapped[AIProviderAdapterKind] = mapped_column(
        Enum(AIProviderAdapterKind, native_enum=False, length=48),
        nullable=False,
    )
    api_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    secret_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[AIProviderStatus] = mapped_column(
        Enum(AIProviderStatus, native_enum=False, length=16),
        default=AIProviderStatus.ENABLED,
        nullable=False,
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    credential_rotated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AIModelConfiguration(Base):
    __tablename__ = "ai_model_configurations"
    __table_args__ = (
        UniqueConstraint(
            "provider_configuration_id",
            "model_key",
            name="uq_ai_model_provider_key",
        ),
        CheckConstraint(
            "max_output_tokens IS NULL OR max_output_tokens > 0",
            name="ck_ai_model_positive_max_output_tokens",
        ),
        Index(
            "ix_ai_model_org_enabled",
            "organization_id",
            "enabled",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    provider_configuration_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ai_provider_configurations.id", ondelete="CASCADE"), nullable=False
    )
    model_key: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    max_output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class AIRequestRecord(Base):
    __tablename__ = "ai_request_records"
    __table_args__ = (
        CheckConstraint(
            "input_char_count >= 0",
            name="ck_ai_request_input_char_count",
        ),
        CheckConstraint(
            "output_char_count IS NULL OR output_char_count >= 0",
            name="ck_ai_request_output_char_count",
        ),
        CheckConstraint(
            "input_tokens IS NULL OR input_tokens >= 0",
            name="ck_ai_request_input_tokens",
        ),
        CheckConstraint(
            "output_tokens IS NULL OR output_tokens >= 0",
            name="ck_ai_request_output_tokens",
        ),
        CheckConstraint(
            "latency_ms IS NULL OR latency_ms >= 0",
            name="ck_ai_request_latency_ms",
        ),
        Index(
            "ix_ai_request_org_created",
            "organization_id",
            "created_at",
        ),
        Index(
            "ix_ai_request_org_status",
            "organization_id",
            "status",
        ),
        Index(
            "ix_ai_request_user_created",
            "user_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    provider_configuration_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ai_provider_configurations.id", ondelete="RESTRICT"), nullable=False
    )
    model_configuration_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ai_model_configurations.id", ondelete="RESTRICT"), nullable=False
    )
    provider_key: Mapped[str] = mapped_column(String(64), nullable=False)
    model_key: Mapped[str] = mapped_column(String(255), nullable=False)
    attribution_node_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("work_graph_nodes.id", ondelete="SET NULL"), nullable=True
    )
    attribution_node_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[AIRequestStatus] = mapped_column(
        Enum(AIRequestStatus, native_enum=False, length=16),
        default=AIRequestStatus.PENDING,
        nullable=False,
    )
    input_char_count: Mapped[int] = mapped_column(Integer, nullable=False)
    output_char_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider_request_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
