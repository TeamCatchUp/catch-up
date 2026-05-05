from unittest import TestCase
from unittest.mock import Mock

from sqlalchemy.dialects import postgresql

from catchup.db.models import SourceType
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
