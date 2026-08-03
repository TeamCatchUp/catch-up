"""published artifact를 검색 projection으로 재투영한다.

검색 인덱스는 원장에서 rebuild 가능한 projection이다. 이 러너가
유일한 전파 경로이며, workspace의 llm_wiki 문서를 전부 지우고
current revision 블록을 다시 넣는다. 나중에 Dreaming Poller가 할
일을 손으로 돌려 보는 것이다.

삭제와 삽입은 한 트랜잭션이 아니다. 삭제가 커밋된 뒤 삽입이 임베더
호출이나 DB에서 넘어지면 그 workspace의 projection은 빈 채로 남는다.
그래도 원장은 멀쩡하므로 러너를 다시 돌리는 것이 복구 경로다 —
인덱스는 canonical이 아니라 언제든 다시 만들 수 있는 사본이다.

개발과 평가 전용이다.

실행:
    uv run python -m catchup.evaluation.run_search_projection_pipeline
    uv run python -m catchup.evaluation.run_search_projection_pipeline \
        --workspace-id 1 --collection-name vectorstore
"""

from __future__ import annotations

import argparse

import structlog
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from catchup.components.embedder.constants import EmbeddingProvider
from catchup.components.embedder.factory import get_embedding_service
from catchup.configs.config import settings
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)
from catchup.knowledge_maintenance.adapters.search.pgvector_projection import (
    PgVectorArtifactSearchProjection,
)
from catchup.knowledge_maintenance.domain.search_projection import ProjectionDocument
from catchup.knowledge_maintenance.domain.search_projection import (
    project_revision_blocks,
)

logger = structlog.get_logger(__name__)


def _collect_documents(
    uow: KnowledgeMaintenanceUnitOfWork,
    *,
    workspace_id: int,
) -> tuple[int, tuple[ProjectionDocument, ...]]:
    """current revision을 읽어 검색 문서로 펼친다.

    저장소는 생성될 때 workspace를 고정하므로 같은 값을 넘겨야 한다.
    다르면 저장소가 ValueError로 막는다.
    """
    with uow:
        revisions = uow.artifacts.find_current_revisions(
            workspace_id=workspace_id
        )

    documents: list[ProjectionDocument] = []
    for revision in revisions:
        documents.extend(
            project_revision_blocks(
                workspace_id=workspace_id,
                artifact_id=revision.artifact_id,
                revision_id=revision.revision_id,
                revision_number=revision.revision_number,
                title=revision.title,
                blocks=revision.blocks,
                created_at=revision.created_at,
            )
        )
    return len(revisions), tuple(documents)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-id", type=int, default=1)
    parser.add_argument(
        "--collection-name",
        default=settings.PGVECTOR_COLLECTION_NAME,
        help="문서를 넣을 pgvector collection 이름을 정한다.",
    )
    args = parser.parse_args()

    engine = create_engine(settings.sqlalchemy_database_url)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    uow = KnowledgeMaintenanceUnitOfWork(
        session_factory,
        workspace_id=args.workspace_id,
    )

    artifact_count, documents = _collect_documents(
        uow, workspace_id=args.workspace_id
    )

    projection = PgVectorArtifactSearchProjection(
        engine=engine,
        embeddings=get_embedding_service(
            EmbeddingProvider.AWS_BEDROCK
        ).get_embedder(),
        collection_name=args.collection_name,
    )
    result = projection.rebuild(
        workspace_id=args.workspace_id,
        documents=documents,
    )

    print("=== Artifact 검색 projection 결과 ===")
    print(f"  collection {args.collection_name}")
    print(f"  artifact {artifact_count} · 블록(문서) {len(documents)}")
    print(f"  삭제 {result.deleted} · 삽입 {result.inserted}")

    logger.info(
        "artifact_search_projection_completed",
        workspace_id=args.workspace_id,
        artifacts=artifact_count,
        documents=len(documents),
        deleted=result.deleted,
        inserted=result.inserted,
    )

    engine.dispose()


if __name__ == "__main__":
    main()
