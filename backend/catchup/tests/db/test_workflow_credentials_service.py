from __future__ import annotations

from unittest import TestCase
from unittest.mock import Mock
from unittest.mock import patch

from catchup.db.models import WorkflowCredential
from catchup.db.models import WorkflowCredentialVendor
from catchup.workflow_credentials.schemas import PersonalOAuthCredentialCreateRequest
from catchup.workflow_credentials.service import WorkflowCredentialService


class WorkflowCredentialServiceTests(TestCase):
    def test_create_commits_service_transaction(self) -> None:
        db = Mock()
        credential = WorkflowCredential()

        with (
            patch(
                "catchup.workflow_credentials.service.encrypt_secret_payload",
                return_value={"access_token": "ciphertext"},
            ),
            patch(
                "catchup.workflow_credentials.service.create_personal_credential",
                return_value=credential,
            ),
        ):
            result = WorkflowCredentialService().create_personal_oauth(
                db,
                PersonalOAuthCredentialCreateRequest(
                    vendor=WorkflowCredentialVendor.ATLASSIAN,
                    workspace_id=1,
                    user_id=2,
                    display_name="Site",
                    external_tenant_id="cloud",
                    external_tenant_name="Site",
                    external_account_id="account",
                    external_account_name="Jane",
                    external_account_email=None,
                    server_url="https://site.atlassian.net",
                    scopes=["read:me"],
                    token_payload={"access_token": "raw-token"},
                ),
            )

        self.assertIs(result, credential)
        db.commit.assert_called_once_with()
        db.refresh.assert_called_once_with(credential)
