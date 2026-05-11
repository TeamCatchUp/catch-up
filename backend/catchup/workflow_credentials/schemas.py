from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from catchup.db.models import WorkflowCredentialAuthType
from catchup.db.models import WorkflowCredentialVendor


class PersonalOAuthCredentialCreateRequest(BaseModel):
    vendor: WorkflowCredentialVendor
    workspace_id: int
    user_id: int
    display_name: str
    external_tenant_id: str
    external_tenant_name: str | None = None
    external_account_id: str
    external_account_name: str | None = None
    external_account_email: str | None = None
    server_url: str | None = None
    scopes: list[str] = Field(default_factory=list)
    token_payload: dict[str, Any]
    extra_metadata: dict[str, Any] | None = None
    expires_in: int | None = None


class PersonalCredentialCreateRequest(BaseModel):
    vendor: WorkflowCredentialVendor
    auth_type: WorkflowCredentialAuthType
    workspace_id: int
    owner_user_id: int
    created_by_user_id: int
    display_name: str
    external_tenant_id: str
    external_tenant_name: str | None = None
    external_account_id: str
    external_account_name: str | None = None
    external_account_email: str | None = None
    server_url: str | None = None
    scopes: list[str] = Field(default_factory=list)
    encrypted_data: dict[str, Any]
    extra_metadata: dict[str, Any] | None = None
    expires_at: datetime | None = None


class WorkflowCredentialResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    display_name: str
    vendor: str
    auth_type: str
    ownership_type: str
    workspace_id: int
    owner_user_id: int | None
    external_tenant_id: str
    external_tenant_name: str | None
    external_account_id: str
    external_account_name: str | None
    external_account_email: str | None
    server_url: str | None
    scopes: list[str]
    capabilities: list[str]
    extra_metadata: dict[str, Any]
    status: str
    expires_at: datetime | None
    last_verified_at: datetime | None
    created_at: datetime
    updated_at: datetime


class WorkflowCredentialListResponse(BaseModel):
    items: list[WorkflowCredentialResponse]
