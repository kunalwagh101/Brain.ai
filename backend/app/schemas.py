import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import MembershipRole


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


class CurrentUserRead(UserRead):
    pass
