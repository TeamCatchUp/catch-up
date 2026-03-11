from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from catchup.audit.enums import AuditLevel
from catchup.auth.schemas import BaseOAuthUserInfoResponse
from catchup.components.auth.constants import OAuthIdentityProviderType
from catchup.components.auth.provider import OAuthIdentityProvider
from catchup.db.models import OAuthUser, UserStatus
from catchup.auth.utils import reformat_name
from catchup.auth.jwt import create_access_token, create_refresh_token
from catchup.db.users import get_oauth_user_with_sub, get_user_by_sub, update_user_refresh_token
from catchup.events.enums import AuthEventAction, EventTopic, EventType
from catchup.audit.service import emit_audit_event


class OAuthService:
    def __init__(
        self, 
        db: Session,
        provider: OAuthIdentityProvider,
        provider_type: OAuthIdentityProviderType = OAuthIdentityProviderType.KEYCLOAK
    ):
        self.db = db
        self.provider = provider
        self.provider_type = provider_type

    def _get_or_register_user(
        self,
        oauth_user: BaseOAuthUserInfoResponse
    ) -> OAuthUser:
        """
        sub 값을 기준으로 로그인 이력이 있는 OAuth 사용자인지 여부를 확인한다.
        만약 처음으로 로그인한 사용자라면 새로 등록한다.
        """
        
        # sub 기반 oauth 유저 조회
        oauth_user_record = get_oauth_user_with_sub(self.db, oauth_user.sub)
        
        if oauth_user_record:
            return oauth_user_record

        # 존재하지 않으면 OAuthUser 레코드 생성
        new_oauth_user = OAuthUser(
            sub=oauth_user.sub,
            email=oauth_user.email,
            name=oauth_user.name,
            status=UserStatus.NEW
        )
        self.db.add(new_oauth_user)
        self.db.flush()

        return new_oauth_user

    async def handle_callback(
        self,
        code: str
    ) -> tuple[str, str | None]:
        """
        OAuth 로그인 후 호출되는 Callback 루틴.
        OAuth IDP로부터 사용자 정보를 획득한 후 access token과 refresh 토큰을 발급한다.
        """
    
        try:

            oauth_user = await self.provider.get_oauth_user_info(code)
            
            def _process_callback_sync():
                oauth_user_record = self._get_or_register_user(oauth_user)
                
                full_name = reformat_name(oauth_user.name)
                
                token_data = {
                    "sub": oauth_user.sub,
                    "email": oauth_user.email,
                    "name": full_name
                }
                access_token = create_access_token(token_data)
                refresh_token = None
                
                if oauth_user_record.user_id is not None:
                    refresh_token = create_refresh_token(token_data)
                    update_user_refresh_token(
                        db=self.db,
                        user_id=oauth_user_record.user_id,
                        refresh_token=refresh_token
                    )

                self.db.commit()
                
                registered_user = get_user_by_sub(self.db, oauth_user.sub)
                snapshot = None
                if registered_user:
                    snapshot = registered_user.to_snapshot()
                    snapshot["sub"] = oauth_user.sub

                emit_audit_event(
                    event_type=EventType.AUTH,
                    event_action=AuthEventAction.LOGIN_SUCCESS,
                    level=AuditLevel.INFO,
                    immediate=True,
                    actor=snapshot,
                )
                
                return access_token, refresh_token
            
            return await run_in_threadpool(_process_callback_sync)
        
        except Exception as e:
            emit_audit_event(
                event_type=EventType.AUTH,
                event_action=AuthEventAction.LOGIN_FAILURE,
                metadata={
                    "reason": "idp_token_exchange_failed",
                    "error": str(e)
                },
                level=AuditLevel.INFO
            )
