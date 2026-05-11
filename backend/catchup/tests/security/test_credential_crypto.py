from __future__ import annotations

from unittest import TestCase
from unittest.mock import patch

from cryptography.fernet import Fernet

from catchup.security import credential_crypto
from catchup.security.credential_crypto import CredentialCryptoError


class CredentialCryptoTests(TestCase):
    def tearDown(self) -> None:
        credential_crypto._get_fernet.cache_clear()

    def test_encrypt_decrypt_round_trip_without_raw_token(self) -> None:
        key = Fernet.generate_key().decode("utf-8")

        with patch.object(
            credential_crypto.settings,
            "WORKFLOW_CREDENTIAL_ENCRYPTION_KEY",
            key,
        ):
            encrypted = credential_crypto.encrypt_secret("xoxp-raw-token")

        self.assertNotIn("xoxp-raw-token", encrypted)

        with patch.object(
            credential_crypto.settings,
            "WORKFLOW_CREDENTIAL_ENCRYPTION_KEY",
            key,
        ):
            self.assertEqual(
                credential_crypto.decrypt_secret(encrypted),
                "xoxp-raw-token",
            )

    def test_missing_key_fails_when_crypto_is_used(self) -> None:
        with patch.object(
            credential_crypto.settings,
            "WORKFLOW_CREDENTIAL_ENCRYPTION_KEY",
            None,
        ):
            with self.assertRaises(CredentialCryptoError):
                credential_crypto.encrypt_secret("secret")
