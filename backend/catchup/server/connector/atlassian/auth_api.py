"""
Atlassian Auth API

Atlassian OAuth 통합 인증 API 엔드포인트.
하나의 OAuth 앱으로 Jira + Confluence 접근 권한을 획득한다.
"""

import logging
import secrets
import base64
import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from httpx import HTTPStatusError, RequestError
from sqlalchemy.orm import Session

from catchup.connectors.atlassian.auth import (
    AtlassianOAuthService,
    get_atlassian_oauth_service,
)
from catchup.connectors.confluence.client import ConfluenceApiClient
from catchup.connectors.confluence.client import ConfluenceAuthError, ConfluenceApiError
from catchup.connectors.confluence.schemas import (
    ConfluenceSpaceResponse,
    ConfluenceUserResponse,
    ConfluenceRoleAssignmentResponse,
)
from catchup.db.confluence import domain_repository as confluence_entities
from catchup.connectors.atlassian.schemas import AtlassianInstallationStatus
from catchup.connectors.jira.factory import create_jira_ingestion_service
from catchup.connectors.jira.dynamic_webhook_service import (
    get_jira_dynamic_webhook_service,
)
from catchup.configs.config import auth_settings, settings
from catchup.db.dependencies import get_db
from catchup.db.engine import SessionLocal
from catchup.db.atlassian import oauth_repository as atlassian_crud
from catchup.utils.redis import store_oauth_state, validate_oauth_state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth/atlassian", tags=["atlassian"])


REQUIRED_CONFLUENCE_SCOPES = {
    "read:confluence-content.all",
    "read:confluence-space.summary",
}
REQUIRED_CONFLUENCE_USER_SCOPES = {
    "read:confluence-user",
}
REQUIRED_CONFLUENCE_ROLE_SCOPES = {
    "read:space:confluence",
    "read:space.permission:confluence",
}
ALL_REQUIRED_CONFLUENCE_SCOPES = (
    REQUIRED_CONFLUENCE_SCOPES
    | REQUIRED_CONFLUENCE_USER_SCOPES
    | REQUIRED_CONFLUENCE_ROLE_SCOPES
)


def _decode_jwt_payload(token: str) -> dict | None:
    """JWT payload를 검증 없이 디코드해 audience/scope 확인용으로 사용."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload_b64 = parts[1]
        padding = "=" * ((4 - len(payload_b64) % 4) % 4)
        payload_bytes = base64.urlsafe_b64decode(payload_b64 + padding)
        return json.loads(payload_bytes.decode("utf-8"))
    except Exception as e:  # pragma: no cover - 진단용 안전 가드
        logger.warning("[ATLASSIAN][AUTH] Failed to decode JWT payload: %s", e)
        return None


# ================================================================
# Endpoints
# ================================================================


@router.get("/install")
async def install_atlassian():
    """
    Atlassian OAuth 설치 시작
    """
    atlassian_service = get_atlassian_oauth_service()
    state = secrets.token_urlsafe(32)

    await store_oauth_state(state, provider="atlassian")

    authorization_url = atlassian_service.get_authorization_url(state=state)
    return RedirectResponse(url=authorization_url)


@router.get("/callback")
async def atlassian_oauth_callback(
    code: str,
    background_tasks: BackgroundTasks,
    state: str | None = None,
    db: Session = Depends(get_db),
    atlassian_service: AtlassianOAuthService = Depends(get_atlassian_oauth_service),
):
    """
    Atlassian OAuth 콜백 처리
    - Authorization code → 토큰 교환
    - 사용자 정보 + 접근 가능한 리소스 조회
    - 리소스별 토큰 저장
    - Jira 동기화/Webhook + Confluence 스텁 작업 등록
    """
    # 동일 cloud_id가 Jira/Confluence 두 리소스로 중복 노출될 수 있어 스코프를 합산 후 처리
    aggregated_resources: dict[str, dict] = {}

    if not state:
        logger.warning("[ATLASSIAN][AUTH] OAuth state 누락")
        return RedirectResponse(
            url=f"{auth_settings.FRONTEND_REDIRECT_URI}?atlassian_installed=false&reason=missing_state"
        )

    is_valid_state = await validate_oauth_state(state, provider="atlassian")
    if not is_valid_state:
        logger.warning(f"[ATLASSIAN][AUTH] OAuth state 검증 실패: {state}")
        return RedirectResponse(
            url=f"{auth_settings.FRONTEND_REDIRECT_URI}?atlassian_installed=false&reason=invalid_state"
        )

    tokens = await atlassian_service.exchange_code_for_tokens(code)
    token_payload = _decode_jwt_payload(tokens.access_token)
    aud_claim = token_payload.get("aud") if token_payload else None
    aud_list = (
        aud_claim if isinstance(aud_claim, list) else [aud_claim] if aud_claim else []
    )
    allowed_audiences = {"api.atlassian.com"}
    if settings.ATLASSIAN_CLIENT_ID:
        allowed_audiences.add(settings.ATLASSIAN_CLIENT_ID)

    if aud_list and not any(aud in allowed_audiences for aud in aud_list):
        logger.warning(
            "[ATLASSIAN][AUTH] Unexpected audience in access token (하지만 진행은 계속합니다): aud=%s, expected one of=%s, scope=%s",
            aud_claim,
            sorted(allowed_audiences),
            (token_payload or {}).get("scope"),
        )
    else:
        logger.info(
            "[ATLASSIAN][AUTH] token_aud=%s, token_scope=%s",
            aud_claim,
            (token_payload or {}).get("scope"),
        )

    user_info = await atlassian_service.get_user_info(tokens.access_token)
    resources = await atlassian_service.get_accessible_resources(tokens.access_token)

    if not resources:
        return RedirectResponse(
            url=f"{auth_settings.FRONTEND_REDIRECT_URI}?atlassian_installed=false&reason=no_resources"
        )

    # 디버그: accessible-resources 리소스/스코프 확인
    resource_debug = [
        {
            "id": r.id,
            "name": r.name,
            "scopes": sorted(r.scopes or []),
        }
        for r in resources
    ]
    logger.info("[ATLASSIAN][AUTH] accessible_resources=%s", resource_debug)

    has_confluence_resource = any(
        any(scope.startswith("read:confluence") or scope.startswith("search:confluence") for scope in (r.scopes or []))
        for r in resources
    )
    if not has_confluence_resource:
        logger.warning(
            "[ATLASSIAN][AUTH] accessible-resources에 Confluence 리소스가 없습니다. Atlassian 사이트/라이선스 또는 앱 권한을 확인하세요."
        )

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=tokens.expires_in)

    for resource in resources:
        resource_scopes = set(resource.scopes or [])
        if resource.id in aggregated_resources:
            aggregated_resources[resource.id]["scopes"] |= resource_scopes
        else:
            aggregated_resources[resource.id] = {
                "resource": resource,
                "scopes": resource_scopes,
            }

    for cloud_id, aggregated in aggregated_resources.items():
        resource = aggregated["resource"]
        resource_scopes = aggregated["scopes"]

        # resource.scopes는 제품별 제한적일 수 있으므로 토큰 스코프까지 합산해 판단
        granted_scopes = resource_scopes | set((tokens.scope or "").split())
        has_confluence_scope = ALL_REQUIRED_CONFLUENCE_SCOPES.issubset(granted_scopes)

        if not has_confluence_scope:
            missing_scopes = sorted(ALL_REQUIRED_CONFLUENCE_SCOPES - granted_scopes)
            logger.warning(
                f"[ATLASSIAN][AUTH] 리소스 스코프 미달로 Confluence 동기화 스킵: "
                f"cloud_id={resource.id}, missing_scopes={missing_scopes}, "
                f"resource_scopes={sorted(resource_scopes)}"
            )
        token_scopes = " ".join(sorted(granted_scopes))

        atlassian_crud.create_or_update_token(
            db=db,
            atlassian_account_id=user_info.account_id,
            cloud_id=cloud_id,
            site_name=resource.name,
            site_url=resource.url,
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            expires_at=expires_at,
            scopes=token_scopes,
        )

        # Jira BackgroundTask
        background_tasks.add_task(_sync_jira_metadata, resource.id)
        background_tasks.add_task(_ensure_jira_dynamic_webhook, resource.id)

        # Confluence BackgroundTask (Phase 2/3 스텁)
        if has_confluence_scope:
            background_tasks.add_task(_sync_confluence_metadata, resource.id)
            background_tasks.add_task(_ensure_confluence_webhook, resource.id)
        else:
            logger.info(
                f"[ATLASSIAN][AUTH] Confluence background task skip: "
                f"cloud_id={resource.id}"
            )

    logger.info(
        f"[ATLASSIAN][AUTH] 설치 완료: {len(resources)}개 사이트 연결 (Jira + Confluence)"
    )

    return RedirectResponse(
        url=f"{auth_settings.FRONTEND_REDIRECT_URI}?atlassian_installed=true&count={len(resources)}"
    )


@router.get("/status", response_model=AtlassianInstallationStatus)
async def atlassian_installation_status(
    db: Session = Depends(get_db),
    atlassian_service: AtlassianOAuthService = Depends(get_atlassian_oauth_service),
):
    """
    Atlassian 설치 상태 조회
    """
    tokens = atlassian_crud.get_all_tokens(db)

    if not tokens:
        return AtlassianInstallationStatus(installed=False)

    try:
        valid_token = await atlassian_service.get_valid_access_token(db, tokens[0])
        resources = await atlassian_service.get_accessible_resources(valid_token)
        return AtlassianInstallationStatus(installed=True, resources=resources)
    except HTTPException as e:
        logger.warning(f"[ATLASSIAN][AUTH] 상태 조회 실패: {e.detail}")
        return AtlassianInstallationStatus(installed=True, resources=[])
    except (HTTPStatusError, RequestError) as e:
        logger.warning(f"[ATLASSIAN][AUTH] API 요청 실패: {e}")
        return AtlassianInstallationStatus(installed=True, resources=[])


@router.delete("/uninstall")
async def atlassian_uninstall(
    cloud_id: str = Query(..., description="삭제할 Atlassian Cloud ID"),
    db: Session = Depends(get_db),
):
    """
    Atlassian 연결 해제
    """
    deleted = atlassian_crud.delete_token(db, cloud_id)
    if deleted:
        return {"status": "success", "message": "Atlassian 연결이 해제되었습니다."}
    return {"status": "not_found", "message": "해당 Atlassian 연결을 찾을 수 없습니다."}


async def _sync_jira_metadata(cloud_id: str) -> None:
    """
    Jira 메타데이터 동기화 (BackgroundTask)
    """
    logger.info(
        f"[ATLASSIAN][AUTH] Starting background metadata sync: cloud_id={cloud_id}"
    )

    db = SessionLocal()
    try:
        service = await create_jira_ingestion_service(db, cloud_id)
        results = await service.sync_metadata(db)
        logger.info(
            f"[ATLASSIAN][AUTH] Background metadata sync completed: "
            f"cloud_id={cloud_id}, results={results}"
        )
    except Exception as e:
        logger.error(
            f"[ATLASSIAN][AUTH] Background metadata sync failed: "
            f"cloud_id={cloud_id}, error={e}"
        )
    finally:
        db.close()


async def _ensure_jira_dynamic_webhook(cloud_id: str) -> None:
    """
    Jira Dynamic Webhook 등록 보장 (BackgroundTask)
    """
    logger.info(
        f"[ATLASSIAN][AUTH] Ensuring Jira dynamic webhook: cloud_id={cloud_id}"
    )

    db = SessionLocal()
    try:
        dynamic_webhook_service = get_jira_dynamic_webhook_service()
        result = await dynamic_webhook_service.ensure_registered(
            db=db, cloud_id=cloud_id
        )
        logger.info(
            f"[ATLASSIAN][AUTH] Jira dynamic webhook ensured: "
            f"cloud_id={cloud_id}, result={result}"
        )
    except Exception as e:
        logger.error(
            f"[ATLASSIAN][AUTH] Jira dynamic webhook ensure failed: "
            f"cloud_id={cloud_id}, error={e}",
            exc_info=True,
        )
    finally:
        db.close()


async def _sync_confluence_metadata(cloud_id: str) -> None:
    """
    Confluence Space 메타데이터 동기화 (BackgroundTask)

    TODO: Phase 2에서 ConfluenceIngestionService + Factory 패턴으로 리팩토링
    """
    logger.info(
        f"[CONFLUENCE][METADATA] Starting Space Sync : cloud_id={cloud_id}"
    )

    db = SessionLocal()
    try:
        token = atlassian_crud.get_token_by_cloud_id(db, cloud_id)
        if not token:
            logger.warning(
                f"[CONFLUENCE][METADATA] No token found: cloud_id={cloud_id}"
            )
            return

        granted_scopes = set((token.scopes or "").split())
        logger.info(
            f"[CONFLUENCE][METADATA] token scopes: cloud_id={cloud_id}, scopes={sorted(granted_scopes)}"
        )
        missing_scopes = sorted(ALL_REQUIRED_CONFLUENCE_SCOPES - granted_scopes)

        if missing_scopes:
            logger.warning(
                f"[CONFLUENCE][METADATA] 스코프 누락으로 동기화 스킵: "
                f"cloud_id={cloud_id}, missing={missing_scopes}, granted={sorted(granted_scopes)}"
            )
            logger.warning(
                f"[CONFLUENCE][METADATA] Confluence 스코프 재인증이 필요합니다. "
                f"권장 스코프: {sorted(ALL_REQUIRED_CONFLUENCE_SCOPES)}"
            )
            return

        atlassian_service = get_atlassian_oauth_service()
        access_token = await atlassian_service.get_valid_access_token(db, token)

        client = ConfluenceApiClient(cloud_id, access_token)

        # 1) 사용자 동기화
        users_data = await client.get_users()
        db_users: list[dict] = []
        for raw_user in users_data:
            try:
                # v1 search API는 {"user": {...}} 형태로 감싸서 반환
                payload = raw_user.get("user") if isinstance(raw_user, dict) else raw_user
                if not payload or not payload.get("accountId"):
                    logger.warning(
                        f"[CONFLUENCE][METADATA] Skip user without accountId: cloud_id={cloud_id}"
                    )
                    continue
                user = ConfluenceUserResponse.model_validate(payload)
                db_users.append(
                    {
                        "cloud_id": cloud_id,
                        "account_id": user.id,
                        "account_type": user.account_type,
                        "display_name": user.display_name,
                        "public_name": user.public_name,
                        "email": user.email,
                        "time_zone": user.time_zone,
                        "locale": user.locale,
                        "avatar_url": user.get_avatar_url(),
                        "is_external_collaborator": user.is_external_collaborator,
                    }
                )
            except Exception as e:
                logger.error(
                    f"[CONFLUENCE][METADATA] Failed to parse user: cloud_id={cloud_id}, error={e}"
                )

        if db_users:
            confluence_entities.upsert_users_bulk(db, db_users)
            logger.info(
                f"[CONFLUENCE][METADATA] Saved {len(db_users)} users: cloud_id={cloud_id}"
            )

        # 2) Space 메타데이터 동기화 (기존)
        spaces_data = await client.get_spaces(space_type=None, status="current")

        logger.info(
            f"[CONFLUENCE][METADATA] Fetched {len(spaces_data)} spaces: "
            f"cloud_id={cloud_id}"
        )

        db_spaces: list[dict] = []
        for raw_space in spaces_data:
            try:
                space = ConfluenceSpaceResponse.model_validate(raw_space)

                description_text = ""
                if space.description:
                    description_text = space.description.get_plain_text()

                db_spaces.append({
                    "cloud_id": cloud_id,
                    "space_id": space.id,
                    "space_key": space.key,
                    "space_name": space.name,
                    "space_type": space.type,
                    "status": space.status,
                    "homepage_id": space.homepage_id,
                    "description": description_text[:2000] if description_text else None,
                })
            except Exception as e:
                logger.error(
                    f"[CONFLUENCE][METADATA] Failed to parse space: "
                    f"cloud_id={cloud_id}, error={e}"
                )

        if db_spaces:
            confluence_entities.upsert_spaces_bulk(db, db_spaces)
            logger.info(
                f"[CONFLUENCE][METADATA] Saved {len(db_spaces)} spaces: "
                f"cloud_id={cloud_id}"
            )

        # 3) Space 멤버(역할) 동기화
        total_members = 0
        role_scope_failed = False
        for space in db_spaces:
            space_id = space["space_id"]
            try:
                assignments = await client.get_space_role_assignments(space_id)
            except ConfluenceAuthError as e:
                if not role_scope_failed:
                    logger.error(
                        f"[CONFLUENCE][METADATA] Role assignment fetch unauthorized (scope?): "
                        f"cloud_id={cloud_id}, space_id={space_id}, error={e}"
                    )
                    role_scope_failed = True
                break
            except ConfluenceApiError as e:
                # RBAC 미지원 사이트에서는 role-assignments가 404. permissions로 폴백.
                status = getattr(e, "status_code", None)
                if status == 404:
                    try:
                        assignments = await client.get_space_permissions(space_id)
                    except Exception as e_perm:
                        logger.error(
                            f"[CONFLUENCE][METADATA] Failed to fetch permissions fallback: "
                            f"cloud_id={cloud_id}, space_id={space_id}, error={e_perm}"
                        )
                        continue
                else:
                    logger.error(
                        f"[CONFLUENCE][METADATA] Failed to fetch role assignments: "
                        f"cloud_id={cloud_id}, space_id={space_id}, error={e}"
                    )
                    continue

            space_members: list[dict] = []
            for raw_assignment in assignments:
                try:
                    if "role" in raw_assignment:
                        assignment = ConfluenceRoleAssignmentResponse.model_validate(raw_assignment)
                        if assignment.principal_type.lower() != "user":
                            continue
                        space_members.append(
                            {
                                "cloud_id": cloud_id,
                                "space_id": space_id,
                                "account_id": assignment.principal_id,
                                "role_id": assignment.role.id,
                                "role_key": assignment.role.key,
                                "role_name": assignment.role.name,
                                "principal_type": assignment.principal_type,
                            }
                        )
                    else:
                        # permissions fallback 구조
                        subject = (raw_assignment or {}).get("subject", {})
                        subj_type = subject.get("type", "")
                        account_id = subject.get("user", {}).get("accountId") if isinstance(subject.get("user"), dict) else None
                        if subj_type.lower() != "user" or not account_id:
                            continue
                        perm_id = str(raw_assignment.get("id", "")) or f"perm:{space_id}"
                        operation = raw_assignment.get("operation", {}) if isinstance(raw_assignment, dict) else {}
                        role_key = operation.get("key")
                        role_name = role_key or operation.get("access")
                        space_members.append(
                            {
                                "cloud_id": cloud_id,
                                "space_id": space_id,
                                "account_id": account_id,
                                "role_id": perm_id,
                                "role_key": role_key,
                                "role_name": role_name,
                                "principal_type": subj_type,
                            }
                        )
                except Exception as e:
                    logger.error(
                        f"[CONFLUENCE][METADATA] Failed to parse role assignment: "
                        f"cloud_id={cloud_id}, space_id={space_id}, error={e}"
                    )

            confluence_entities.delete_space_members_by_space(db, cloud_id, space_id)
            if space_members:
                confluence_entities.upsert_space_members_bulk(db, space_members)
                total_members += len(space_members)
                logger.info(
                    f"[CONFLUENCE][METADATA] Saved {len(space_members)} members for space_id={space_id}"
                )

        if db_spaces:
            logger.info(
                f"[CONFLUENCE][METADATA] Completed member sync: cloud_id={cloud_id}, members={total_members}"
            )

    except ConfluenceAuthError as e:
        logger.warning(
            f"[CONFLUENCE][METADATA] 인증/권한 오류: cloud_id={cloud_id}, "
            f"error={e}. "
            "Confluence 스코프(read:confluence-*) 또는 사용자 권한(공간 접근 권한)을 확인하세요."
        )
    except ConfluenceApiError as e:
        logger.error(
            f"[CONFLUENCE][METADATA] API 요청 실패: "
            f"cloud_id={cloud_id}, status={getattr(e, 'status_code', None)}, error={e}",
            exc_info=True,
        )
    except Exception as e:
        logger.error(
            f"[CONFLUENCE][METADATA] Space sync failed: "
            f"cloud_id={cloud_id}, error={e}",
            exc_info=True,
        )
    finally:
        db.close()



async def _ensure_confluence_webhook(cloud_id: str) -> None:
    """
    Confluence Webhook 등록 보장 (BackgroundTask)

    TODO: Phase 3에서 Confluence webhook 등록/갱신으로 확장
    (현재 스텁 로그만 남기며, 추후 이벤트 동기화 정책 정합성 점검 필요).
    """
    logger.info(
        f"[ATLASSIAN][AUTH] Confluence webhook ensure skipped (Phase 3): "
        f"cloud_id={cloud_id}"
    )
