"""이름 벡터 캐시 포트를 PostgreSQL 표로 구현한다.

해소의 transaction과 session을 나눠 쓴다. 캐시는 다시 만들 수 있는 사본이라
해소가 도중에 되돌아가도 담아 둔 벡터까지 함께 지울 이유가 없고, 반대로
캐시 저장이 실패해도 해소 transaction을 더럽히면 안 되기 때문이다. 그래서
호출마다 session을 열고 닫는다.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from collections.abc import Mapping
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from catchup.db.models import KnowledgeNameEmbedding as KnowledgeNameEmbeddingRow

UNIQUE_CONSTRAINT = "uq_knowledge_name_embeddings_name"


class SqlAlchemyNameEmbeddingCache:
    """정규화 이름 단위로 벡터를 담고 찾는다.

    담긴 벡터는 정본이 아니라 다시 만들 수 있는 사본이다. 표를 통째로
    비워도 다음 라운드가 임베딩을 다시 불러 같은 값을 채우므로 잃는 사실이
    없다.

    벡터를 JSONB 실수 배열로 담고 색인은 UNIQUE 제약이 만드는 것 하나뿐이다.
    여기서 하는 일은 이름으로 정확히 찾아오는 조회지 가까운 벡터를 훑는 ANN
    검색이 아니라, pgvector 컬럼도 HNSW 색인도 필요하지 않다.
    """

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        """session을 만들 자리를 받아 캐시를 만든다."""
        self._session_factory = session_factory

    def lookup(
        self,
        *,
        workspace_id: int,
        model_id: str,
        normalized_names: Sequence[str],
    ) -> dict[str, tuple[float, ...]]:
        """담아 둔 이름의 벡터만 골라 돌려준다.

        Returns:
            찾은 이름만 담은 사전을 준다. 없는 이름은 키 자체가 없어,
            부르는 쪽이 빠진 이름만 임베딩한다.
        """
        wanted = list(dict.fromkeys(normalized_names))
        if not wanted:
            return {}

        session = self._session_factory()
        try:
            rows = session.execute(
                select(
                    KnowledgeNameEmbeddingRow.normalized_name,
                    KnowledgeNameEmbeddingRow.vector,
                ).where(
                    KnowledgeNameEmbeddingRow.workspace_id == workspace_id,
                    KnowledgeNameEmbeddingRow.model_id == model_id,
                    KnowledgeNameEmbeddingRow.normalized_name.in_(wanted),
                )
            ).all()
        finally:
            session.close()

        return {
            name: tuple(float(value) for value in vector)
            for name, vector in rows
        }

    def store(
        self,
        *,
        workspace_id: int,
        model_id: str,
        vectors: Mapping[str, Sequence[float]],
    ) -> None:
        """새로 얻은 벡터를 담는다.

        같은 키가 이미 있으면 그대로 둔다. 같은 이름·같은 모델이면 값도
        같으므로 덮어쓸 이유가 없고, 두 실행이 겹쳐도 한쪽이 UNIQUE 충돌로
        실패하지 않아야 한다.
        """
        rows = [
            {
                "id": uuid.uuid4(),
                "workspace_id": workspace_id,
                "model_id": model_id,
                "normalized_name": name,
                "vector": [float(value) for value in vector],
            }
            for name, vector in vectors.items()
        ]
        if not rows:
            return

        session = self._session_factory()
        try:
            session.execute(
                pg_insert(KnowledgeNameEmbeddingRow)
                .values(rows)
                .on_conflict_do_nothing(constraint=UNIQUE_CONSTRAINT)
            )
            session.commit()
        finally:
            session.close()
