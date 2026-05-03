from __future__ import annotations

from unittest import TestCase

from catchup.audit.actions import IntegrationAction
from catchup.audit.base import AuditStatus
from catchup.audit.metadata import ChannelTalkCredentialAuditMetadata
from catchup.audit.utils import AuditLogMetadataInput
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkConnectRequest,
)
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkCredentialsStatus,
)
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkUninstallResult,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentAssociationStatus,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentConnectRequest,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentCredentialsStatus,
)


def _sample_func() -> None:
    return None


def _metadata_input(
    *,
    action: IntegrationAction,
    arguments: dict[str, object],
    result: object,
) -> AuditLogMetadataInput:
    return AuditLogMetadataInput(
        func=_sample_func,
        arguments=arguments,
        status=AuditStatus.SUCCESS,
        action=action,
        result=result,
    )


class ChannelTalkCredentialAuditMetadataTests(TestCase):
    def assertSecretsExcluded(
        self,
        payload: dict[str, object],
        *secret_values: str,
    ) -> None:
        payload_text = repr(payload)
        for secret_value in secret_values:
            self.assertNotIn(secret_value, payload_text)

    def test_channel_credentials_metadata_excludes_secret_values(self) -> None:
        request = ChannelTalkConnectRequest(
            access_key="secret-access-key",
            access_secret="secret-access-secret",
            webhook_token="secret-webhook-token",
        )
        result = ChannelTalkCredentialsStatus(
            installed=True,
            channel_id="channel-123",
            channel_name="Support",
            webhook_token_configured=True,
        )

        metadata = ChannelTalkCredentialAuditMetadata.from_channel_credentials_audit(
            _metadata_input(
                action=IntegrationAction.CONNECT_CREDENTIALS,
                arguments={"connect_request": request},
                result=result,
            )
        )

        payload = metadata.model_dump(exclude_none=True)
        self.assertEqual(payload["provider"], "channel_talk")
        self.assertEqual(payload["credential_type"], "channel")
        self.assertEqual(payload["result_status"], "success")
        self.assertEqual(payload["channel_id"], "channel-123")
        self.assertTrue(payload["webhook_token_configured"])
        self.assertNotIn("access_key", payload)
        self.assertNotIn("access_secret", payload)
        self.assertNotIn("webhook_token", payload)
        self.assertSecretsExcluded(
            payload,
            "secret-access-key",
            "secret-access-secret",
            "secret-webhook-token",
        )

    def test_document_credentials_metadata_records_association(self) -> None:
        request = ChannelTalkDocumentConnectRequest(
            access_key="document-access-key",
            access_secret="document-access-secret",
            polling_cycle_hours=6,
        )
        result = ChannelTalkDocumentCredentialsStatus(
            installed=True,
            channel_id="channel-123",
            space_id="space-456",
            space_name="Docs",
            association_status=ChannelTalkDocumentAssociationStatus.API_VERIFIED,
            polling_cycle_hours=6,
        )

        metadata = ChannelTalkCredentialAuditMetadata.from_document_credentials_audit(
            _metadata_input(
                action=IntegrationAction.VALIDATE_CREDENTIALS,
                arguments={"connect_request": request},
                result=result,
            )
        )

        self.assertEqual(metadata.credential_type, "documents")
        self.assertEqual(metadata.channel_id, "channel-123")
        self.assertEqual(metadata.space_id, "space-456")
        self.assertEqual(metadata.association_status, "api_verified")
        self.assertEqual(metadata.polling_cycle_hours, 6)

    def test_uninstall_not_found_status_is_explicit(self) -> None:
        metadata = ChannelTalkCredentialAuditMetadata.from_channel_credentials_audit(
            _metadata_input(
                action=IntegrationAction.UNINSTALL_CREDENTIALS,
                arguments={"channel_id": "channel-123"},
                result=ChannelTalkUninstallResult(removed=False),
            )
        )

        self.assertEqual(metadata.channel_id, "channel-123")
        self.assertEqual(metadata.result_status, "not_found")
        self.assertFalse(metadata.removed)
