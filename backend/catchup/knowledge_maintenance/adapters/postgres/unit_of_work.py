from __future__ import annotations

from collections.abc import Callable
from types import TracebackType
from typing import Self

from sqlalchemy.orm import Session

from catchup.knowledge_maintenance.adapters.postgres.repositories import (
    SqlAlchemySourceVersionRepository,
)


class SqlAlchemySourceVersionUnitOfWork:
    """SourceVersion 수집의 transaction 경계를 SQLAlchemy session으로 구현한다."""

    source_versions: SqlAlchemySourceVersionRepository

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None

    def __enter__(self) -> Self:
        session = self._session_factory()
        self._session = session
        self.source_versions = SqlAlchemySourceVersionRepository(session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        session = self._session
        self._session = None
        if session is None:
            return
        # commit하지 않고 빠져나간 변경은 남기지 않는다.
        session.rollback()
        session.close()

    def commit(self) -> None:
        """현재 transaction을 커밋한다."""
        if self._session is None:
            raise RuntimeError("UnitOfWork를 with 블록 안에서 사용해야 한다.")
        self._session.commit()
