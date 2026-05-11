from __future__ import annotations

from functools import lru_cache
from typing import Any

from cryptography.fernet import Fernet
from cryptography.fernet import InvalidToken

from catchup.configs.config import settings


class CredentialCryptoError(RuntimeError):
    """Raised when Workflow Credential encryption is unavailable or invalid."""


def ensure_workflow_credential_encryption_ready() -> None:
    _get_fernet()


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    key = settings.WORKFLOW_CREDENTIAL_ENCRYPTION_KEY
    if not key:
        raise CredentialCryptoError(
            "WORKFLOW_CREDENTIAL_ENCRYPTION_KEY is required for Workflow Credentials"
        )

    try:
        return Fernet(key.encode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise CredentialCryptoError(
            "WORKFLOW_CREDENTIAL_ENCRYPTION_KEY must be a valid Fernet key"
        ) from exc


def encrypt_secret(value: str) -> str:
    if not value:
        raise CredentialCryptoError("Cannot encrypt an empty secret value")
    return _get_fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str) -> str:
    try:
        return _get_fernet().decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise CredentialCryptoError("Encrypted Workflow Credential payload is invalid") from exc


def encrypt_secret_payload(payload: dict[str, Any]) -> dict[str, Any]:
    encrypted: dict[str, Any] = {}
    for key, value in payload.items():
        if value is None:
            continue
        encrypted[key] = encrypt_secret(value) if isinstance(value, str) else value
    return encrypted
