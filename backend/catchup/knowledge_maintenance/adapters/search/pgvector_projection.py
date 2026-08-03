"""langchain_pg_embedding에 검색 projection을 쓰는 adapter다.

langchain import는 이 모듈에만 존재한다 — domain·services가 vector DB
구현체를 모르게 하는 port 경계가 여기다.
"""

from __future__ import annotations

from collections.abc import Sequence

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_postgres import PGVector
from sqlalchemy import Engine
from sqlalchemy import delete as sa_delete
from sqlalchemy import select

from catchup.knowledge_maintenance.domain.search_projection import SOURCE
from catchup.knowledge_maintenance.domain.search_projection import ProjectionDocument
from catchup.knowledge_maintenance.ports.search_projection import (
    ProjectionRebuildResult,
)


class PgVectorArtifactSearchProjection:
    """workspace 단위 전량 교체로 검색 projection을 다시 만든다."""

    def __init__(
        self,
        *,
        engine: Engine,
        embeddings: Embeddings,
        collection_name: str,
    ) -> None:
        self._collection_name = collection_name
        self._store = PGVector(
            embeddings=embeddings,
            collection_name=collection_name,
            connection=engine,
            use_jsonb=True,
        )

    def rebuild(
        self,
        *,
        workspace_id: int,
        documents: Sequence[ProjectionDocument],
    ) -> ProjectionRebuildResult:
        """workspace의 llm_wiki 문서를 지우고 새 문서를 넣는다.

        부분 upsert가 아니라 전량 교체인 이유는 document_id에
        revision_id가 없기 때문이다. 블록이 사라진 새 판을 upsert하면
        낡은 판의 블록이 그대로 남아 검색에 잡힌다.
        """
        deleted = self._delete_workspace_documents(workspace_id)

        if documents:
            self._store.add_documents(
                [
                    Document(
                        page_content=document.content,
                        metadata=dict(document.metadata),
                        id=document.document_id,
                    )
                    for document in documents
                ],
                ids=[document.document_id for document in documents],
            )

        return ProjectionRebuildResult(
            deleted=deleted, inserted=len(documents)
        )

    def _delete_workspace_documents(self, workspace_id: int) -> int:
        """이 collection 안의 해당 workspace llm_wiki 행을 지운다."""
        embedding_store = self._store.EmbeddingStore
        collection_store = self._store.CollectionStore
        statement = sa_delete(embedding_store).where(
            embedding_store.collection_id.in_(
                select(collection_store.uuid).where(
                    collection_store.name == self._collection_name
                )
            ),
            embedding_store.cmetadata["source"].astext == SOURCE,
            embedding_store.cmetadata["scope_id"].astext == str(workspace_id),
        )

        with self._store._make_sync_session() as session:
            result = session.execute(statement)
            session.commit()

        return result.rowcount or 0
