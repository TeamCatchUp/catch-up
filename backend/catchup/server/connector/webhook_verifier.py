"""
Webhook verification provider.

- GitHub: HMAC SHA256
- Slack: HMAC SHA256 + request timestamp window
- Jira: OAuth JWT
"""

import hashlib
import hmac
import time
from dataclasses import dataclass
from typing import Optional

import jwt
from jwt import InvalidTokenError


@dataclass(slots=True)
class VerifyResult:
    ok: bool
    reason: str


class WebhookVerifierProvider:
    @staticmethod
    def verify_github(
        payload_body: bytes,
        signature_header: Optional[str],
        secret: str,
    ) -> VerifyResult:
        if not signature_header:
            return VerifyResult(ok=False, reason="missing_signature")

        expected_signature = "sha256=" + hmac.new(
            secret.encode("utf-8"),
            payload_body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected_signature, signature_header):
            return VerifyResult(ok=False, reason="signature_mismatch")

        return VerifyResult(ok=True, reason="ok")

    @staticmethod
    def verify_slack(
        payload_body: bytes,
        signature: Optional[str],
        timestamp: Optional[str],
        signing_secret: str,
        tolerance_seconds: int = 300,
    ) -> VerifyResult:
        if not signature:
            return VerifyResult(ok=False, reason="missing_signature")
        if not timestamp:
            return VerifyResult(ok=False, reason="missing_timestamp")

        try:
            request_ts = int(timestamp)
        except ValueError:
            return VerifyResult(ok=False, reason="invalid_timestamp_format")

        current_ts = int(time.time())
        if abs(current_ts - request_ts) > tolerance_seconds:
            return VerifyResult(ok=False, reason="timestamp_out_of_window")

        sig_basestring = f"v0:{timestamp}:{payload_body.decode('utf-8')}"
        expected_signature = "v0=" + hmac.new(
            signing_secret.encode("utf-8"),
            sig_basestring.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected_signature, signature):
            return VerifyResult(ok=False, reason="signature_mismatch")

        return VerifyResult(ok=True, reason="ok")

    @staticmethod
    def verify_jira(
        authorization: Optional[str],
        client_secret: str,
        jwt_leeway_seconds: int = 30,
    ) -> VerifyResult:
        if not authorization or not authorization.startswith("Bearer "):
            return VerifyResult(ok=False, reason="missing_bearer_token")

        token = authorization.removeprefix("Bearer ").strip()
        if not token:
            return VerifyResult(ok=False, reason="empty_bearer_token")

        try:
            jwt.decode(
                jwt=token,
                key=client_secret,
                algorithms=["HS256"],
                options={"verify_aud": False, "require": ["exp"]},
                leeway=jwt_leeway_seconds,
            )
        except InvalidTokenError as exc:
            return VerifyResult(
                ok=False,
                reason=f"invalid_jwt:{exc.__class__.__name__}",
            )

        return VerifyResult(ok=True, reason="ok")
