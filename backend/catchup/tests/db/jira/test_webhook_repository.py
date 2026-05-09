from datetime import datetime
from datetime import timezone
from unittest import TestCase
from unittest.mock import Mock
from unittest.mock import patch

from sqlalchemy.dialects import postgresql

from catchup.db.jira.webhook_repository import upsert_webhook


class JiraWebhookRepositoryTests(TestCase):
    def test_upsert_webhook_uses_atomic_conflict_handling(self) -> None:
        db = Mock()
        persisted = Mock()

        with patch(
            "catchup.db.jira.webhook_repository.get_webhook",
            return_value=persisted,
        ) as get_webhook:
            result = upsert_webhook(
                db=db,
                cloud_id="cloud-1",
                webhook_id=123,
                callback_url="https://example.com/jira/webhook/cloud-1",
                jql_filter='project IN ("ABC")',
                events=["jira:issue_updated", "jira:issue_created"],
                expires_at=datetime(2026, 5, 9, tzinfo=timezone.utc),
                last_synced_at=datetime(2026, 5, 9, 6, 20, tzinfo=timezone.utc),
            )

        self.assertIs(result, persisted)
        db.execute.assert_called_once()
        db.flush.assert_called_once()
        self.assertFalse(db.add.called)
        get_webhook.assert_called_once_with(db, "cloud-1", 123)

        statement = db.execute.call_args.args[0]
        compiled = str(statement.compile(dialect=postgresql.dialect()))
        self.assertIn(
            "ON CONFLICT ON CONSTRAINT "
            "uq_jira_webhook_subscriptions_cloud_webhook DO UPDATE",
            compiled,
        )
        self.assertIn("callback_url = %(param_1)s", compiled)
        self.assertIn("last_synced_at = %(param_5)s", compiled)
