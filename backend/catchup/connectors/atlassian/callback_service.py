"""
Atlassian OAuth 콜백 도메인 서비스 (프레임워크 비종속)
- state 검증
- code → token 교환
- aud 체크
- accessible resources 스코프 집계
- 토큰 저장
- Jira/Confluence 동기화 타깃 산출
"""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Sequence

from sqlalchemy.orm import Session

from catchup.connectors.atlassian.constants import (
    REQUIRED_CONFLUENCE_SCOPES,
    REQUIRED_JIRA_SCOPES,
)
from catchup.connectors.atlassian.oauth_client import AtlassianOAuthService
from catchup.configs.config import settings
from catchup.db.atlassian import oauth_repository as atlassian_crud
from catchup.utils.redis import validate_oauth_state

logger = logging.getLogger(__name__)


# -------------------------
# 도메인 예외
# -------------------------

class CallbackError(Exception):
    def __init__(self, code: str, detail: str | None = None):
        self.code = code
        self.detail = detail
        super().__init__(detail or code)


class StateInvalid(CallbackError):
    def __init__(self):
        super().__init__("invalid_state")


class ResourceFetchFailed(CallbackError):
    def __init__(self, detail: str | None = None):
        super().__init__("resource_fetch_failed", detail)


class NoResourcesFound(CallbackError):
    def __init__(self):
        super().__init__("no_resources")


# -------------------------
# DTO
# -------------------------

@dataclass
class CallbackResult:
    resources: Sequence[Any]
    confluence_targets: list[str]
    jira_targets: list[str]


# -------------------------
# 내부 유틸
# -------------------------

def _decode_jwt_payload(token: str) -> dict | None:
    try:
        header, payload, sig = token.split(".")
        padding = "=" * ((4 - len(payload) % 4) % 4)
        return json.loads(base64.urlsafe_b64decode(payload + padding).decode("utf-8"))
    except Exception as e:  # pragma: no cover
        logger.warning("[ATLASSIAN][AUTH] Failed to decode JWT payload: %s", e)
        return None


def _aggregate_scope(resources: Sequence[Any], token_scope: str) -> dict[str, set[str]]:
    """
    cloud_id별로 token.scope ∪ resource.scopes 합집합을 계산한다.
    부수 기능 없이 스코프 집계만 수행.
    """
    token_scope_set = set((token_scope or "").split())
    aggregated: dict[str, set[str]] = {}

    for resource in resources:
        cloud_id = resource.id
        resource_scopes = set(resource.scopes or [])
        aggregated[cloud_id] = resource_scopes | token_scope_set

    return aggregated


def _check_audience(token_payload: dict | None) -> None:
    aud_claim = token_payload.get("aud") if token_payload else None

    if isinstance(aud_claim, list):
        aud_list = aud_claim
    elif aud_claim:
        aud_list = [aud_claim]
    else:
        aud_list = []

    allowed_audiences = {"api.atlassian.com"}
    if settings.ATLASSIAN_CLIENT_ID:
        allowed_audiences.add(settings.ATLASSIAN_CLIENT_ID)

    has_allowed = aud_list and any(aud in allowed_audiences for aud in aud_list)

    if not aud_list:
        logger.info(
            "[ATLASSIAN][AUTH] Access token has no aud claim; skipping audience check. scope=%s",
            (token_payload or {}).get("scope"),
        )
    elif has_allowed:
        logger.info(
            "[ATLASSIAN][AUTH] token_aud=%s, token_scope=%s",
            aud_claim,
            (token_payload or {}).get("scope"),
        )
    else:
        logger.warning(
            "[ATLASSIAN][AUTH] Unexpected audience in access token (하지만 진행은 계속합니다): aud=%s, expected=%s, scope=%s",
            aud_claim,
            sorted(allowed_audiences),
            (token_payload or {}).get("scope"),
        )


# -------------------------
# 서비스
# -------------------------

class AtlassianCallbackService:
    """콜백 비즈니스 로직 담당 서비스 (FastAPI 비의존)."""

    def __init__(self, oauth_service: AtlassianOAuthService):
        self.oauth_service = oauth_service

    async def handle_callback(
        self,
        *,
        db: Session,
        code: str,
        state: str | None,
    ) -> CallbackResult:
        # 1) state 검증
        invalid_state = (state is None) or (not await validate_oauth_state(state, provider="atlassian"))
        if invalid_state:
            raise StateInvalid()

        # 2) code -> token 교환
        tokens = await self.oauth_service.exchange_code_for_tokens(code)
        token_payload = _decode_jwt_payload(tokens.access_token)
        _check_audience(token_payload)

        # 3) 사용자 / 리소스 조회
        try:
            user_info = await self.oauth_service.get_user_info(tokens.access_token)
            resources = await self.oauth_service.get_accessible_resources(tokens.access_token)
        except Exception as e:
            raise ResourceFetchFailed(str(e)) from e

        if not resources:
            raise NoResourcesFound()

        expires_at = datetime.now(timezone.utc) + timedelta(seconds=tokens.expires_in)

        aggregated_scopes = _aggregate_scope(resources, tokens.scope)
        confluence_targets: list[str] = []
        jira_targets: list[str] = []

        # 4) cloud_id별 토큰 저장 + 동기화 대상 결정
        for cloud_id, granted in aggregated_scopes.items():
            has_confluence = REQUIRED_CONFLUENCE_SCOPES.issubset(granted)
            has_jira = REQUIRED_JIRA_SCOPES.issubset(granted)

            if has_confluence:
                confluence_targets.append(cloud_id)
            if has_jira:
                jira_targets.append(cloud_id)

            # 리소스 메타는 accessible-resources에서 바로 찾는다
            resource = next((r for r in resources if r.id == cloud_id), None)
            site_name = resource.name if resource else None
            site_url = resource.url if resource else None

            atlassian_crud.create_or_update_token(
                db=db,
                atlassian_account_id=user_info.account_id,
                cloud_id=cloud_id,
                site_name=site_name,
                site_url=site_url,
                access_token=tokens.access_token,
                refresh_token=tokens.refresh_token,
                expires_at=expires_at,
                scopes=" ".join(sorted(granted)),
            )

        return CallbackResult(
            resources=resources,
            confluence_targets=confluence_targets,
            jira_targets=jira_targets,
        )
