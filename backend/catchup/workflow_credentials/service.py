from __future__ import annotations

from datetime import datetime
from datetime import timedelta
from datetime import timezone

from sqlalchemy.orm import Session

from catchup.db.models import WorkflowCredential
from catchup.db.models import WorkflowCredentialAuthType
from catchup.db.workflow_credentials import PersonalCredentialAlreadyExists
from catchup.db.workflow_credentials import create_personal_credential
from catchup.db.workflow_credentials import list_active_personal_credentials
from catchup.db.workflow_credentials import soft_delete_owned_personal_credential
from catchup.security.credential_crypto import encrypt_secret_payload
from catchup.workflow_credentials.schemas import PersonalCredentialCreateRequest
from catchup.workflow_credentials.schemas import PersonalOAuthCredentialCreateRequest


class WorkflowCredentialAlreadyExists(ValueError):
    """Raised when a personal OAuth credential is already connected."""


class WorkflowCredentialService:

    def list_for_user(self, db: Session, *, user_id: int) -> list[WorkflowCredential]:
        return list_active_personal_credentials(db, owner_user_id=user_id)

    def delete_for_user(
        self,
        db: Session,
        *,
        credential_id: int,
        user_id: int,
    ) -> bool:
        deleted = soft_delete_owned_personal_credential(
            db,
            credential_id=credential_id,
            owner_user_id=user_id,
        )
        if deleted:
            db.commit()
        return deleted

    def create_personal_oauth(
        self,
        db: Session,
        request: PersonalOAuthCredentialCreateRequest,
    ) -> WorkflowCredential:
        expires_at = None
        if request.expires_in is not None:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=request.expires_in)

        try:
            credential = create_personal_credential(
                db,
                PersonalCredentialCreateRequest(
                    vendor=request.vendor,
                    auth_type=WorkflowCredentialAuthType.OAUTH2_USER,
                    workspace_id=request.workspace_id,
                    owner_user_id=request.user_id,
                    created_by_user_id=request.user_id,
                    display_name=request.display_name,
                    external_tenant_id=request.external_tenant_id,
                    external_tenant_name=request.external_tenant_name,
                    external_account_id=request.external_account_id,
                    external_account_name=request.external_account_name,
                    external_account_email=request.external_account_email,
                    server_url=request.server_url,
                    scopes=sorted(set(request.scopes)),
                    encrypted_data=encrypt_secret_payload(request.token_payload),
                    extra_metadata=request.extra_metadata,
                    expires_at=expires_at,
                ),
            )
        except PersonalCredentialAlreadyExists as exc:
            raise WorkflowCredentialAlreadyExists(str(exc)) from exc

        db.commit()
        db.refresh(credential)
        return credential
