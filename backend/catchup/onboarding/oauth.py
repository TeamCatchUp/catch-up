import asyncio
import logging

from catchup.components.auth.keycloak_admin import KeycloakAdminClient
from catchup.db.engine import SessionLocal
from catchup.db.user_source_mapping import delete_deactivated_oauth_users, upsert_oauth_users
from catchup.mapping.schemas import OAuthUserSchema
from catchup.configs.config import auth_settings
from catchup.utils.client import get_global_async_client


logger = logging.getLogger(__name__)


async def sync_initial_keycloak_users():
    try:
        kc_admin = KeycloakAdminClient(
            client=get_global_async_client(),
            server_url=auth_settings.KC_INTERNAL_URL,
            realm=auth_settings.KC_REALM,
            client_id=auth_settings.KC_CLIENT_ID,
            client_secret=auth_settings.KC_CLIENT_SECRET
        )
        raw_users_data = await kc_admin.get_parsed_users()
        
        parsed_users = [OAuthUserSchema.model_validate(user) for user in raw_users_data]
        
        if not parsed_users:
            logger.warning(f"No users found from OAuth")
            return
        
        def _upsert_oauth_users_sync():
            with SessionLocal() as db:
                try:
                    upsert_oauth_users(db, parsed_users)
                    delete_deactivated_oauth_users(db)
                    db.commit()
                    logger.info(f"Successfully synced {len(parsed_users)} users from Keycloak")
                except Exception as e:
                    db.rollback()
                    logger.error(f"DB Upsert failed: {e}")
                    raise
                
        await asyncio.to_thread(_upsert_oauth_users_sync)

    except Exception as e:
        logger.error(f"Failed to sync OAuth users: {e}", exc_info=True)