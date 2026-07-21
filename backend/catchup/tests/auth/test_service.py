from unittest import TestCase
from unittest.mock import Mock
from unittest.mock import patch

from fastapi import HTTPException

from catchup.auth.schemas import BaseOAuthUserInfoResponse
from catchup.auth.service import OAuthService
from catchup.db.models import UserStatus


class OAuthServiceRegistrationPolicyTests(TestCase):
    def setUp(self) -> None:
        self.db = Mock()
        self.service = OAuthService(db=self.db, provider=Mock())
        self.oauth_user = BaseOAuthUserInfoResponse(
            sub="keycloak-sub",
            email="new-user@example.com",
            name="New User",
        )

    @patch("catchup.auth.service.has_admin_ever_onboarded", return_value=True)
    @patch("catchup.auth.service.get_oauth_user_with_sub", return_value=None)
    def test_rejects_unsynced_user_after_admin_onboarding(
        self,
        _get_oauth_user: Mock,
        _has_admin: Mock,
    ) -> None:
        with self.assertRaises(HTTPException) as raised:
            self.service._get_or_register_user(self.oauth_user)

        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(
            raised.exception.detail,
            "관리자에 의해 등록되지 않은 사용자입니다.",
        )
        self.db.add.assert_not_called()

    @patch("catchup.auth.service.has_admin_ever_onboarded", return_value=False)
    @patch("catchup.auth.service.get_oauth_user_with_sub", return_value=None)
    def test_allows_first_admin_candidate_before_admin_onboarding(
        self,
        _get_oauth_user: Mock,
        _has_admin: Mock,
    ) -> None:
        created = self.service._get_or_register_user(self.oauth_user)

        self.assertEqual(created.sub, "keycloak-sub")
        self.assertEqual(created.email, "new-user@example.com")
        self.assertEqual(created.status, UserStatus.NEW)
        self.db.add.assert_called_once_with(created)
        self.db.flush.assert_called_once_with()
