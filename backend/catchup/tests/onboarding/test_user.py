from unittest import TestCase
from unittest.mock import Mock
from unittest.mock import patch

from catchup.db.models import JobLevel
from catchup.db.models import User
from catchup.onboarding.schemas import UserSignUpSchema
from catchup.onboarding.user import register_user_from_oauth


class UserOnboardingTests(TestCase):
    @patch("catchup.onboarding.user.create_missing_user_source_mappings_by_email")
    @patch("catchup.onboarding.user.resolve_pending_source_mappings")
    @patch("catchup.onboarding.user.add_user_to_workspace")
    @patch("catchup.onboarding.user.get_workspace_by_id", return_value=object())
    @patch("catchup.onboarding.user.get_oauth_user_with_sub")
    def test_signup_matches_all_collaboration_accounts_after_user_creation(
        self,
        get_oauth_user: Mock,
        _get_workspace: Mock,
        _add_to_workspace: Mock,
        _resolve_pending: Mock,
        create_missing_mappings: Mock,
    ) -> None:
        db = Mock()
        oauth_user = Mock(user_id=None)
        get_oauth_user.return_value = oauth_user

        def assign_user_id(instance: object) -> None:
            if isinstance(instance, User):
                instance.id = 8

        db.add.side_effect = assign_user_id
        payload = UserSignUpSchema(
            sub="keycloak-sub",
            email="new-user@example.com",
            name="New User",
            department="engineering",
            job_level=JobLevel.MEMBER,
        )

        created = register_user_from_oauth(db, payload)

        self.assertEqual(created.id, 8)
        self.assertEqual(oauth_user.user_id, 8)
        create_missing_mappings.assert_called_once_with(
            db,
            user_id=8,
            email="new-user@example.com",
        )
        db.commit.assert_called_once_with()
