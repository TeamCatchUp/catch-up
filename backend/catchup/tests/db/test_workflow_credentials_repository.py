from __future__ import annotations

from unittest import TestCase
from unittest.mock import Mock

from catchup.db.models import WorkflowCredential
from catchup.db.models import WorkflowCredentialAuthType
from catchup.db.models import WorkflowCredentialStatus
from catchup.db.models import WorkflowCredentialVendor
from catchup.db.workflow_credentials import PersonalCredentialAlreadyExists
from catchup.db.workflow_credentials import create_personal_credential
from catchup.db.workflow_credentials import soft_delete_owned_personal_credential
from catchup.workflow_credentials.schemas import PersonalCredentialCreateRequest


def _create_request(**overrides) -> PersonalCredentialCreateRequest:
    values = {
        "vendor": WorkflowCredentialVendor.SLACK,
        "auth_type": WorkflowCredentialAuthType.OAUTH2_USER,
        "workspace_id": 1,
        "owner_user_id": 2,
        "created_by_user_id": 2,
        "display_name": "Slack",
        "external_tenant_id": "T123",
        "external_tenant_name": "Team",
        "external_account_id": "U123",
        "external_account_name": None,
        "external_account_email": None,
        "server_url": None,
        "scopes": ["users:read"],
        "encrypted_data": {"access_token": "ciphertext"},
    }
    values.update(overrides)
    return PersonalCredentialCreateRequest(**values)


class WorkflowCredentialRepositoryTests(TestCase):
    def test_create_sets_personal_defaults_and_empty_capabilities(self) -> None:
        db = Mock()
        db.scalar.return_value = None

        credential = create_personal_credential(db, _create_request())

        db.add.assert_called_once_with(credential)
        self.assertEqual(credential.created_by_user_id, 2)
        self.assertEqual(credential.capabilities, [])
        self.assertEqual(credential.status, WorkflowCredentialStatus.ACTIVE)

    def test_create_rejects_existing_identity(self) -> None:
        db = Mock()
        existing = WorkflowCredential(
            vendor=WorkflowCredentialVendor.GITHUB,
            auth_type=WorkflowCredentialAuthType.OAUTH2_USER,
            workspace_id=1,
            owner_user_id=2,
            created_by_user_id=99,
            display_name="old",
            external_tenant_id="github.com",
            external_account_id="123",
        )
        db.scalar.return_value = existing

        with self.assertRaises(PersonalCredentialAlreadyExists):
            create_personal_credential(
                db,
                _create_request(
                    vendor=WorkflowCredentialVendor.GITHUB,
                    display_name="octocat",
                    external_tenant_id="github.com",
                    external_tenant_name="GitHub",
                    external_account_id="123",
                    external_account_name="octocat",
                    server_url="https://api.github.com",
                    scopes=[],
                    encrypted_data={"access_token": "new-ciphertext"},
                ),
            )

        self.assertFalse(db.add.called)
        self.assertEqual(existing.created_by_user_id, 99)
        self.assertEqual(existing.display_name, "old")

    def test_soft_delete_clears_secret_payload(self) -> None:
        db = Mock()
        credential = WorkflowCredential(
            vendor=WorkflowCredentialVendor.ATLASSIAN,
            auth_type=WorkflowCredentialAuthType.OAUTH2_USER,
            workspace_id=1,
            owner_user_id=2,
            created_by_user_id=2,
            display_name="Site",
            external_tenant_id="cloud",
            external_account_id="account",
            encrypted_data={"access_token": "ciphertext"},
        )
        db.scalar.return_value = credential

        deleted = soft_delete_owned_personal_credential(
            db,
            credential_id=1,
            owner_user_id=2,
        )

        self.assertTrue(deleted)
        self.assertEqual(credential.status, WorkflowCredentialStatus.REVOKED)
        self.assertEqual(credential.encrypted_data, {})
