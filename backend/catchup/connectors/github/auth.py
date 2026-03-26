"""
GitHub App Authentication Service

GitHub App 인증을 담당하는 서비스.
- JWT 생성 (Private Key 서명)
- Installation Access Token 발급
- App 정보 조회
"""

import base64
from datetime import datetime, timezone
import time
from binascii import Error as BinasciiError
from functools import lru_cache
from pathlib import Path

import httpx
import jwt
from cryptography.hazmat.primitives import serialization

from catchup.configs.config import settings


class GitHubAppService:
    '''
    GithubApp 인증 서비스
    - JWT 객체 생성 (Private Key 서명)
    - Installation Access Token 발급
    '''

    GITHUB_API_BASE = "https://api.github.com"

    def __init__(
            self,
            app_id: int,
            private_key: str):
        self.app_id = app_id
        self.private_key = private_key
        self._installation_tokens: dict[int, tuple[str, float]] = {}

    def _create_jwt(self) -> str:
        """
        GitHub App 인증용 JWT 생성
        - Time Out : 10분
        - Signing Algorithm : RS256
        """
        now = int(time.time())
        payload = {
            "iat": now - 60,
            "exp": now + (10 * 60),  # 10분
            "iss": str(self.app_id),  # JWT iss 클레임은 문자열이어야 함
        }
        return jwt.encode(payload, self.private_key, algorithm="RS256")

    async def get_installation_access_token(
        self,
        installation_id: int,
        *,
        force_refresh: bool = False,
    ) -> str:
        """
        Installation Access Token 발급
        - 유효 시간: 1시간
        - Repository 접근에 사용

        Returns:
            Access Token 문자열 (ghs_xxx...)
        """
        now = time.time()
        cached = self._installation_tokens.get(installation_id)
        if not force_refresh and cached is not None:
            token, expires_at = cached
            if expires_at - now > 60:
                return token

        jwt_token = self._create_jwt()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.GITHUB_API_BASE}/app/installations/{installation_id}/access_tokens",
                headers={
                    "Authorization": f"Bearer {jwt_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            response.raise_for_status()
            data = response.json()
            expires_at = _parse_github_token_expiry(data.get("expires_at"))
            self._installation_tokens[installation_id] = (data["token"], expires_at)
            return data["token"]

    async def get_app_info(self) -> dict:
        """GitHub App 정보 조회 (Health Check)"""
        jwt_token = self._create_jwt()

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.GITHUB_API_BASE}/app",
                headers={
                    "Authorization": f"Bearer {jwt_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            response.raise_for_status()
            return response.json()


def _load_private_key() -> str:
    """환경변수에 저장된 Private Key를 읽어 반환"""
    private_key = settings.GITHUB_APP_PRIVATE_KEY.strip()

    if not private_key:
        raise ValueError("GITHUB_APP_PRIVATE_KEY NOT FOUND.")

    private_key = _resolve_private_key_source(private_key)
    private_key = _normalize_private_key(private_key)
    _validate_private_key(private_key)
    return private_key


def _resolve_private_key_source(value: str) -> str:
    candidate = value.strip()

    if len(candidate) >= 2 and candidate[0] == candidate[-1] and candidate[0] in {"'", '"'}:
        candidate = candidate[1:-1].strip()

    if "\n" in candidate or "\\n" in candidate:
        return candidate

    if len(candidate) > 255:
        return candidate

    key_path = Path(candidate).expanduser()
    looks_like_path = (
        "/" in candidate
        or "\\" in candidate
        or candidate.startswith(".")
        or key_path.suffix.lower() in {".pem", ".key"}
    )
    if looks_like_path and key_path.is_file():
        return key_path.read_text(encoding="utf-8").strip()

    return candidate


def _normalize_private_key(value: str) -> str:
    candidate = value.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\r", "\n").strip()

    if "-----BEGIN" in candidate:
        return candidate

    try:
        decoded = base64.b64decode(candidate, validate=True).decode("utf-8").strip()
    except (BinasciiError, UnicodeDecodeError):
        return candidate

    return decoded


def _validate_private_key(value: str) -> None:
    if "-----BEGIN" not in value or "-----END" not in value:
        raise ValueError(
            "GITHUB_APP_PRIVATE_KEY must be a complete PEM private key. "
            "Raw PEM, escaped \\n PEM, base64-encoded PEM, or a readable PEM file path are supported."
        )

    try:
        serialization.load_pem_private_key(value.encode("utf-8"), password=None)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "GITHUB_APP_PRIVATE_KEY is not a valid PEM private key. "
            "Check that the key was copied completely and was not truncated in .env."
        ) from exc


def _parse_github_token_expiry(value: object) -> float:
    if not isinstance(value, str) or not value.strip():
        return time.time() + 300

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
            timezone.utc
        ).timestamp()
    except ValueError:
        return time.time() + 300


@lru_cache
def get_github_app_service() -> GitHubAppService:
    """GitHubAppService 싱글톤 팩토리"""
    private_key = _load_private_key()
    return GitHubAppService(
        app_id=settings.GITHUB_APP_ID,
        private_key=private_key,
    )
