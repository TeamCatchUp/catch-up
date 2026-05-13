from datetime import datetime
from datetime import timedelta
from unittest import TestCase
from unittest.mock import MagicMock

from catchup.db.manual_search_history import get_search_queries_by_user
from catchup.db.manual_search_history import save_search_query
from catchup.db.models import ManualSearchHistory


class SaveSearchQueryTests(TestCase):
    def test_save_adds_record_to_session(self):
        db = MagicMock()
        record = save_search_query(db, user_id=1, query="슬랙 알림")

        db.add.assert_called_once()
        added = db.add.call_args.args[0]
        assert isinstance(added, ManualSearchHistory)
        assert added.user_id == 1
        assert added.query == "슬랙 알림"

    def test_save_returns_manual_search_history_instance(self):
        db = MagicMock()
        record = save_search_query(db, user_id=7, query="jira 이슈")

        assert isinstance(record, ManualSearchHistory)
        assert record.user_id == 7
        assert record.query == "jira 이슈"

    def test_save_does_not_commit(self):
        db = MagicMock()
        save_search_query(db, user_id=1, query="test")

        db.commit.assert_not_called()


class GetSearchQueriesByUserTests(TestCase):
    def _make_db(self, items=None, total=0):
        db = MagicMock()
        db.scalar.return_value = total
        db.scalars.return_value.all.return_value = items or []
        return db

    def test_returns_tuple_of_items_and_total(self):
        db = self._make_db(items=[], total=0)
        result = get_search_queries_by_user(db, user_id=1)

        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_total_comes_from_scalar(self):
        db = self._make_db(total=42)
        _, total = get_search_queries_by_user(db, user_id=1)

        assert total == 42

    def test_items_are_listed(self):
        record = MagicMock(spec=ManualSearchHistory)
        db = self._make_db(items=[record], total=1)
        items, _ = get_search_queries_by_user(db, user_id=1)

        assert items == [record]

    def test_period_all_does_not_add_date_filter(self):
        db = self._make_db()
        get_search_queries_by_user(db, user_id=1, period="all")

        # scalar for count, scalars for items — both should be called
        db.scalar.assert_called_once()
        db.scalars.assert_called_once()

    def test_scalar_returns_zero_on_none(self):
        db = MagicMock()
        db.scalar.return_value = None
        db.scalars.return_value.all.return_value = []
        _, total = get_search_queries_by_user(db, user_id=1)

        assert total == 0
