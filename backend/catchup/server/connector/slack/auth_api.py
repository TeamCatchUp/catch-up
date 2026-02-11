import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from httpx import HTTPStatusError, RequestError
from sqlalchemy.orm import Session

from catchup.connectors.slack.auth import get_slack_oauth_service, SlackOAuthService
from catchup.connectors.slack.schemas import (
    SlackInstallationStatus,
    SlackWorkspaceInfo,
)
from catchup.configs.config import auth_settings
from catchup.db.dependencies import get_db
from catchup.db.slack import oauth_repository as slack_crud
from catchup.utils.redis import store_oauth_state, validate_oauth_state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth/slack", tags=["slack"])


@router.get("/install")
async def install_slack():
    slack_service = get_slack_oauth_service()
    state = secrets.token_urlsafe(32)

    await store_oauth_state(state, provider="slack")

    authorization_url = slack_service.get_authorization_url(state=state)
    return RedirectResponse(url=authorization_url)


@router.get("/callback")
async def slack_oauth_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
    slack_service: SlackOAuthService = Depends(get_slack_oauth_service),
):
    """
    Slack OAuth 콜백 처리
    - Authorization code → 토큰 교환
    - Workspace 정보 저장
    """
    # 에러 처리 (사용자가 취소한 경우)
    if error:
        logger.warning(f"Slack OAuth 에러: {error}")
        return RedirectResponse(
            url=f"{auth_settings.FRONTEND_REDIRECT_URI}?slack_installed=false&reason={error}"
        )

    if not code:
        return RedirectResponse(
            url=f"{auth_settings.FRONTEND_REDIRECT_URI}?slack_installed=false&reason=no_code"
        )

    # State 파라미터 검증 (CSRF 방지)
    if not state:
        logger.warning("Slack OAuth state 파라미터 누락")
        return RedirectResponse(
            url=f"{auth_settings.FRONTEND_REDIRECT_URI}?slack_installed=false&reason=missing_state"
        )

    is_valid_state = await validate_oauth_state(state, provider="slack")
    if not is_valid_state:
        logger.warning(f"Slack OAuth state 검증 실패: {state}")
        return RedirectResponse(
            url=f"{auth_settings.FRONTEND_REDIRECT_URI}?slack_installed=false&reason=invalid_state"
        )

    # 1. Code → Token 교환
    tokens = await slack_service.exchange_code_for_tokens(code)

    # 2. Token Rotation 사용 시 만료 시간 계산
    bot_expires_at = None
    if tokens.expires_in:
        bot_expires_at = datetime.now(timezone.utc) + timedelta(seconds=tokens.expires_in)

    # 3. Token 저장
    slack_crud.create_or_update_slack_token(
        db=db,
        team_id=tokens.team.id,
        team_name=tokens.team.name,
        bot_user_id=tokens.bot_user_id,
        bot_access_token=tokens.access_token,
        bot_scopes=tokens.scope,
        authed_user_id=tokens.authed_user.id if tokens.authed_user else None,
        bot_refresh_token=tokens.refresh_token,
        bot_token_expires_at=bot_expires_at,
        incoming_webhook_url=tokens.incoming_webhook.url if tokens.incoming_webhook else None,
        incoming_webhook_channel=tokens.incoming_webhook.channel if tokens.incoming_webhook else None,
    )

    logger.info(f"Slack 설치 완료: Team ID = {tokens.team.id}, Name = {tokens.team.name}")

    # 4. 프론트엔드로 리다이렉트
    return RedirectResponse(
        url=f"{auth_settings.FRONTEND_REDIRECT_URI}?slack_installed=true&team_name={tokens.team.name}"
    )


@router.get("/status", response_model=SlackInstallationStatus)
async def slack_installation_status(
    db: Session = Depends(get_db),
    slack_service: SlackOAuthService = Depends(get_slack_oauth_service),
):
    """Slack 설치 상태 조회"""
    tokens = slack_crud.get_all_slack_tokens(db)

    if not tokens:
        return SlackInstallationStatus(installed=False)

    workspaces = []
    for token in tokens:
        try:
            # 토큰 유효성 확인
            valid_token = await slack_service.get_valid_access_token(db, token)
            await slack_service.test_auth(valid_token)

            workspaces.append(SlackWorkspaceInfo(
                team_id=token.team_id,
                team_name=token.team_name or "",
                bot_user_id=token.bot_user_id,
                scopes=token.bot_scopes.split() if token.bot_scopes else [],
                connected_at=token.created_at,
            ))
        except HTTPException as e:
            logger.warning(f"Slack 상태 조회 실패 (Team: {token.team_id}): {e.detail}")
            # 토큰이 유효하지 않더라도 연결된 것으로 표시
            workspaces.append(SlackWorkspaceInfo(
                team_id=token.team_id,
                team_name=token.team_name or "",
                bot_user_id=token.bot_user_id,
                scopes=[],
                connected_at=token.created_at,
            ))
        except (HTTPStatusError, RequestError) as e:
            logger.warning(f"Slack API 요청 실패 (Team: {token.team_id}): {e}")
            workspaces.append(SlackWorkspaceInfo(
                team_id=token.team_id,
                team_name=token.team_name or "",
                bot_user_id=token.bot_user_id,
                scopes=[],
                connected_at=token.created_at,
            ))

    return SlackInstallationStatus(installed=True, workspaces=workspaces)


@router.delete("/uninstall")
async def slack_uninstall(
    team_id: str = Query(..., description="삭제할 Slack Team ID"),
    revoke_token: bool = Query(default=True, description="Token 취소 여부"),
    db: Session = Depends(get_db),
    slack_service: SlackOAuthService = Depends(get_slack_oauth_service),
):
    """Slack 연결 해제"""
    token = slack_crud.get_slack_token_by_team_id(db, team_id)

    if not token:
        return {"status": "not_found", "message": "해당 Slack 연결을 찾을 수 없습니다."}

    if revoke_token:
        try:
            await slack_service.revoke_token(token.bot_access_token)
            logger.info(f"Slack Token 취소 완료: Team ID = {team_id}")
        except HTTPException as e:
            logger.warning(f"Slack Token 취소 실패: {e.detail}")
        except (HTTPStatusError, RequestError) as e:
            logger.warning(f"Slack API 요청 실패 (Token 취소): {e}")

    deleted = slack_crud.delete_slack_token(db, team_id)
    if deleted:
        return {"status": "success", "message": "Slack 연결이 해제되었습니다."}

    return {"status": "error", "message": "연결 해제 중 오류가 발생했습니다."}
