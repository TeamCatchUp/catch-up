from unittest import TestCase
from unittest.mock import Mock
from unittest.mock import call
from unittest.mock import patch

from sqlalchemy.dialects import postgresql

from catchup.db.models import SourceType
from catchup.db.user_source_mapping import create_missing_user_source_mappings_by_email
from catchup.db.user_source_mapping import insert_user_source_mapping_if_absent


class UserSourceMappingRepositoryTests(TestCase):
    def test_insert_if_absent_uses_atomic_conflict_handling(self) -> None:
        db = Mock()
        db.execute.return_value.rowcount = 1

        inserted = insert_user_source_mapping_if_absent(
            db,
            user_id=1,
            source_type=SourceType.JIRA,
            external_user_identifier="account-1",
        )

        self.assertTrue(inserted)
        db.execute.assert_called_once()
        self.assertFalse(db.scalar.called)
        self.assertFalse(db.add.called)
        statement = db.execute.call_args.args[0]
        compiled = str(statement.compile(dialect=postgresql.dialect()))
        self.assertIn("ON CONFLICT ON CONSTRAINT uq_user_source DO NOTHING", compiled)

    def test_insert_if_absent_returns_false_when_conflict_skips_insert(self) -> None:
        db = Mock()
        db.execute.return_value.rowcount = 0

        inserted = insert_user_source_mapping_if_absent(
            db,
            user_id=1,
            source_type=SourceType.JIRA,
            external_user_identifier="account-1",
        )

        self.assertFalse(inserted)

    @patch("catchup.db.user_source_mapping.insert_user_source_mapping_if_absent")
    @patch("catchup.db.user_source_mapping.find_external_user_id_by_email_case_insensitive")
    def test_create_missing_mappings_checks_every_collaboration_user_table(
        self,
        find_external_user_id: Mock,
        insert_mapping: Mock,
    ) -> None:
        db = Mock()
        identifiers = {
            SourceType.SLACK: "U123",
            SourceType.JIRA: "jira-123",
            SourceType.CONFLUENCE: "confluence-123",
            SourceType.GITHUB: "octocat",
            SourceType.CHANNEL_TALK: "manager-123",
        }
        find_external_user_id.side_effect = (
            lambda _db, source_type, _email: identifiers[source_type]
        )
        insert_mapping.return_value = True

        created = create_missing_user_source_mappings_by_email(
            db,
            user_id=8,
            email="New-User@example.com",
        )

        self.assertEqual(created, identifiers)
        self.assertEqual(
            find_external_user_id.call_args_list,
            [
                call(db, source_type, "New-User@example.com")
                for source_type in identifiers
            ],
        )
        self.assertEqual(insert_mapping.call_count, len(identifiers))
