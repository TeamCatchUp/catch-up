from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock
from unittest.mock import patch

from catchup.onboarding.oauth import sync_initial_keycloak_users


class OAuthUserSyncTests(IsolatedAsyncioTestCase):
    @patch(
        "catchup.onboarding.oauth.KeycloakAdminClient.get_parsed_users",
        new_callable=AsyncMock,
        side_effect=RuntimeError("keycloak unavailable"),
    )
    async def test_sync_propagates_keycloak_failure(self, _get_users: AsyncMock) -> None:
        with self.assertRaisesRegex(RuntimeError, "keycloak unavailable"):
            await sync_initial_keycloak_users()
