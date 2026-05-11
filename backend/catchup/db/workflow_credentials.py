from __future__ import annotations

from datetime import datetime
from datetime import timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from catchup.db.models import WorkflowCredential
from catchup.db.models import WorkflowCredentialOwnershipType
from catchup.db.models import WorkflowCredentialStatus
from catchup.workflow_credentials.schemas import PersonalCredentialCreateRequest


class PersonalCredentialAlreadyExists(ValueError):
    """Raised when a personal credential identity already exists."""


def create_personal_credential(
    db: Session,
    request: PersonalCredentialCreateRequest,
) -> WorkflowCredential:
    existing = db.scalar(
        select(WorkflowCredential)
        .where(
            WorkflowCredential.vendor == request.vendor,
            WorkflowCredential.auth_type == request.auth_type,
            WorkflowCredential.workspace_id == request.workspace_id,
            WorkflowCredential.owner_user_id == request.owner_user_id,
            WorkflowCredential.external_tenant_id == request.external_tenant_id,
            WorkflowCredential.external_account_id == request.external_account_id,
            WorkflowCredential.ownership_type
            == WorkflowCredentialOwnershipType.USER_PERSONAL,
        )
        .with_for_update()
    )

    if existing is not None:
        raise PersonalCredentialAlreadyExists(
            "Workflow personal credential already exists"
        )

    credential = WorkflowCredential(
        vendor=request.vendor,
        auth_type=request.auth_type,
        ownership_type=WorkflowCredentialOwnershipType.USER_PERSONAL,
        workspace_id=request.workspace_id,
        owner_user_id=request.owner_user_id,
        created_by_user_id=request.created_by_user_id,
        external_tenant_id=request.external_tenant_id,
        external_account_id=request.external_account_id,
    )
    _apply_personal_credential_update(credential, request)
    db.add(credential)
    return credential


def _apply_personal_credential_update(
    credential: WorkflowCredential,
    request: PersonalCredentialCreateRequest,
) -> None:
    credential.display_name = request.display_name
    credential.external_tenant_name = request.external_tenant_name
    credential.external_account_name = request.external_account_name
    credential.external_account_email = request.external_account_email
    credential.server_url = request.server_url
    credential.scopes = request.scopes
    credential.capabilities = []
    credential.encrypted_data = request.encrypted_data
    credential.extra_metadata = request.extra_metadata or {}
    credential.expires_at = request.expires_at
    credential.status = WorkflowCredentialStatus.ACTIVE
    credential.last_verified_at = datetime.now(timezone.utc)


def list_active_personal_credentials(
    db: Session,
    *,
    owner_user_id: int,
) -> list[WorkflowCredential]:
    return list(
        db.scalars(
            select(WorkflowCredential)
            .where(
                WorkflowCredential.owner_user_id == owner_user_id,
                WorkflowCredential.ownership_type
                == WorkflowCredentialOwnershipType.USER_PERSONAL,
                WorkflowCredential.status != WorkflowCredentialStatus.REVOKED,
            )
            .order_by(WorkflowCredential.created_at.desc())
        )
    )


def soft_delete_owned_personal_credential(
    db: Session,
    *,
    credential_id: int,
    owner_user_id: int,
) -> bool:
    credential = db.scalar(
        select(WorkflowCredential).where(
            WorkflowCredential.id == credential_id,
            WorkflowCredential.owner_user_id == owner_user_id,
            WorkflowCredential.ownership_type
            == WorkflowCredentialOwnershipType.USER_PERSONAL,
        )
    )
    if credential is None:
        return False

    # TODO: Revoke the token with the vendor once revoke integration is designed.
    credential.status = WorkflowCredentialStatus.REVOKED
    credential.encrypted_data = {}
    return True
