from __future__ import annotations

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from catchup.db.models import SourceVersionRow
from catchup.knowledge_maintenance.adapters.postgres.mappers import source_identity_hash
from catchup.knowledge_maintenance.adapters.postgres.mappers import to_domain
from catchup.knowledge_maintenance.adapters.postgres.mappers import to_row
from catchup.knowledge_maintenance.domain.source_version import SourceIdentity
from catchup.knowledge_maintenance.domain.source_version import SourceVersion


class SqlAlchemySourceVersionRepository:
    """SourceVersion 영속성을 PostgreSQL로 구현한다."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_idempotency_key(
        self,
        *,
        workspace_id: int,
        idempotency_key: str,
    ) -> SourceVersion | None:
        """같은 전달 키로 이미 저장된 SourceVersion을 찾는다."""
        row = self._session.scalar(
            select(SourceVersionRow).where(
                SourceVersionRow.workspace_id == workspace_id,
                SourceVersionRow.idempotency_key == idempotency_key,
            )
        )
        return to_domain(row) if row is not None else None

    def get_by_source_version(
        self,
        *,
        workspace_id: int,
        source_type: str,
        source_identity: SourceIdentity,
        source_version_key: str,
    ) -> SourceVersion | None:
        """같은 원문의 같은 버전이 이미 저장됐는지 찾는다."""
        row = self._session.scalar(
            select(SourceVersionRow).where(
                SourceVersionRow.workspace_id == workspace_id,
                SourceVersionRow.source_type == source_type,
                SourceVersionRow.source_identity_hash
                == source_identity_hash(source_identity),
                SourceVersionRow.source_version_key == source_version_key,
            )
        )
        return to_domain(row) if row is not None else None

    def get_latest_for_source(
        self,
        *,
        workspace_id: int,
        source_type: str,
        source_identity: SourceIdentity,
    ) -> SourceVersion | None:
        """같은 원문에서 가장 최근에 갱신된 SourceVersion을 찾는다."""
        row = self._session.scalar(
            select(SourceVersionRow)
            .where(
                SourceVersionRow.workspace_id == workspace_id,
                SourceVersionRow.source_type == source_type,
                SourceVersionRow.source_identity_hash
                == source_identity_hash(source_identity),
            )
            .order_by(
                func.coalesce(
                    SourceVersionRow.source_updated_at,
                    SourceVersionRow.observed_at,
                ).desc()
            )
            .limit(1)
        )
        return to_domain(row) if row is not None else None

    def add(self, source_version: SourceVersion) -> None:
        """SourceVersion을 현재 transaction에 추가한다."""
        self._session.add(to_row(source_version))
