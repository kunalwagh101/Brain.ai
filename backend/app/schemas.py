import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import (
    IntegrationHealth,
    IntegrationStatus,
    MembershipRole,
    ResourceAccessLevel,
    SourceIdentityState,
)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str | None


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    slug: str = Field(pattern=r"^[a-z0-9](?:[a-z0-9-]{0,78}[a-z0-9])?$", max_length=80)


class OrganizationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str
    created_at: datetime


class MembershipCreate(BaseModel):
    user_email: str = Field(min_length=3, max_length=320)
    role: MembershipRole = MembershipRole.MEMBER


class MembershipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    user_id: uuid.UUID
    role: MembershipRole
    created_at: datetime


class ResourceGrantCreate(BaseModel):
    resource_type: str = Field(pattern=r"^[a-z][a-z0-9_.-]{0,63}$", max_length=64)
    resource_id: str = Field(min_length=1, max_length=255)
    user_id: uuid.UUID
    access: ResourceAccessLevel


class ResourceGrantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    resource_type: str
    resource_id: str
    user_id: uuid.UUID
    access: ResourceAccessLevel
    created_by_user_id: uuid.UUID
    created_at: datetime


class IntegrationConnectionCreate(BaseModel):
    provider: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,39}$", max_length=40)
    external_account_id: str = Field(min_length=1, max_length=255)
    display_name: str = Field(min_length=1, max_length=160)
    scopes: list[str] = Field(default_factory=list, max_length=64)
    credentials: dict[str, str] = Field(min_length=1, max_length=32)

    @field_validator("scopes")
    @classmethod
    def normalize_scopes(cls, scopes: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for scope in scopes:
            value = scope.strip()
            if not value or len(value) > 255:
                raise ValueError("Scopes must be non-empty and at most 255 characters")
            if value not in seen:
                seen.add(value)
                normalized.append(value)
        return normalized

    @field_validator("credentials")
    @classmethod
    def validate_credentials(cls, credentials: dict[str, str]) -> dict[str, str]:
        cleaned: dict[str, str] = {}
        for key, value in credentials.items():
            name = key.strip()
            if not name or len(name) > 128:
                raise ValueError("Credential names must be 1-128 characters")
            if not value or len(value) > 16384:
                raise ValueError("Credential values must be 1-16384 characters")
            cleaned[name] = value
        return cleaned


class IntegrationConnectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    provider: str
    external_account_id: str
    display_name: str
    status: IntegrationStatus
    health: IntegrationHealth
    scopes: list[str]
    provider_metadata: dict[str, object]
    sync_cursor: str | None
    last_synced_at: datetime | None
    last_error_code: str | None
    created_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    revoked_at: datetime | None


class SlackInstallRead(BaseModel):
    authorization_url: str
    scopes: list[str]


class SlackChannelRead(BaseModel):
    id: str
    name: str
    is_private: bool
    is_member: bool


class SlackChannelPage(BaseModel):
    channels: list[SlackChannelRead]
    next_cursor: str | None


class SlackChannelAuthorizationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    integration_connection_id: uuid.UUID
    channel_id: str
    channel_name: str
    is_private: bool
    member_ids: list[str]
    backfill_cursor: str | None
    backfill_complete: bool
    last_backfilled_at: datetime | None
    authorized_by_user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class SlackBackfillRequest(BaseModel):
    cursor: str | None = Field(default=None, max_length=2048)
    limit: int = Field(default=15, ge=1, le=15)
    reset: bool = False


class SlackBackfillRead(BaseModel):
    inserted: int
    duplicates: int
    next_cursor: str | None
    complete: bool


class GitHubInstallRead(BaseModel):
    installation_url: str


class GitHubInstallationCandidate(BaseModel):
    installation_id: int
    account_login: str
    target_type: str
    repository_selection: str
    selection_token: str


class GitHubOAuthCallbackRead(BaseModel):
    installations: list[GitHubInstallationCandidate]


class GitHubConnectRequest(BaseModel):
    selection_token: str = Field(min_length=16, max_length=8192)


class GitHubBackfillRequest(BaseModel):
    cursor: str | None = Field(default=None, max_length=2048)
    page_size: int = Field(default=30, ge=1, le=100)
    reset: bool = False


class GitHubBackfillRead(BaseModel):
    inserted: int
    duplicates: int
    canonicalized: int
    quarantined: int
    next_cursor: str | None
    complete: bool
    repository: str | None
    resource: str | None


class SourceIdentityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    provider: str
    external_id: str
    display_name: str | None
    email: str | None
    email_verified: bool
    state: SourceIdentityState
    resolved_user_id: uuid.UUID | None
    resolution_method: str | None
    first_seen_at: datetime
    last_seen_at: datetime
    created_at: datetime
    updated_at: datetime


class IdentityResolutionHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    source_identity_id: uuid.UUID
    previous_user_id: uuid.UUID | None
    new_user_id: uuid.UUID | None
    action: str
    method: str
    actor_user_id: uuid.UUID | None
    evidence: dict[str, object]
    created_at: datetime


class SourceIdentityResolveRequest(BaseModel):
    user_id: uuid.UUID
    reason: str | None = Field(default=None, max_length=500)


class SourceIdentityUnresolveRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class IdentityReconcileRequest(BaseModel):
    limit: int = Field(default=200, ge=1, le=500)


class IdentityReconcileRead(BaseModel):
    processed: int
    remaining: int


class CurrentUserRead(UserRead):
    pass
