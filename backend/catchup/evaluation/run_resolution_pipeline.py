"""pending entity 후보를 canonical identity로 해소한다.

`run_extraction_pipeline.py`의 다음 단계다. 저쪽이 Observation에서 후보를
뽑는다면, 이 스크립트는 쌓인 후보를 결정론 병합(즉시 적용), 관찰이
하나뿐인 이름의 승격(즉시 적용), 후보가 여럿인 이름의 LLM 판정
(proposal)으로 해소한다. 행 2 Resolution의 첫 슬라이스를 손으로 돌려
보는 것이다.

`KNOWLEDGE_AUTO_MERGE_ENABLED`가 켜져 있으면 해소가 병합 proposal을
시스템 이름으로 승인하고, 이 스크립트가 곧바로 적용까지 이어서 돌린다.
꺼져 있으면 승인도 적용도 하지 않고 proposal을 계류로 남긴다.

여러 번 돌려도 안전하다. 해소된 후보는 스캔에서 빠지고, proposal은
그룹당 pending 하나만 유지된다.

개발과 평가 전용이다.

실행:
    uv run python -m catchup.evaluation.run_resolution_pipeline
    uv run python -m catchup.evaluation.run_resolution_pipeline --skip-judge
"""

from __future__ import annotations

import argparse

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from catchup.components.embedder.constants import EmbeddingProvider
from catchup.components.embedder.factory import get_embedding_service
from catchup.components.llm.constants import LlmProvider
from catchup.components.llm.constants import ModelCapacity
from catchup.components.llm.factory import get_llm_service
from catchup.configs.config import settings
from catchup.knowledge_maintenance.adapters.llm.identity_judge import (
    BedrockIdentityJudge,
)
from catchup.knowledge_maintenance.adapters.llm.name_embedder import (
    EmbeddingServiceNameEmbedder,
)
from catchup.knowledge_maintenance.adapters.llm.name_embedder import (
    cached_name_embedder,
)
from catchup.knowledge_maintenance.adapters.llm.structured_extractor import CONTRACT_ID
from catchup.knowledge_maintenance.adapters.postgres.name_embedding_cache import (
    SqlAlchemyNameEmbeddingCache,
)
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)
from catchup.knowledge_maintenance.contracts.extraction import EntityTypeEntry
from catchup.knowledge_maintenance.services.apply_mutation_proposals import (
    apply_mutation_proposals,
)
from catchup.knowledge_maintenance.services.converge_vocabulary import (
    resolve_latest_published_version,
)
from catchup.knowledge_maintenance.services.resolve_entity_candidates import (
    resolve_entity_candidates,
)


def _resolve_vocabulary_version(
    uow: KnowledgeMaintenanceUnitOfWork,
    *,
    workspace_id: int,
) -> str | None:
    """최신 발행본 어휘 버전을 고른다."""
    with uow:
        return resolve_latest_published_version(
            uow.ontology.list_versions(
                workspace_id=workspace_id,
                ontology_id=CONTRACT_ID,
            )
        )


def _load_entity_types(
    uow: KnowledgeMaintenanceUnitOfWork,
    *,
    workspace_id: int,
    version: str,
) -> tuple[EntityTypeEntry, ...]:
    """발행된 어휘 스냅샷에서 entity 종류 사전을 읽는다.

    스냅샷이 없으면 무엇을 찾았는지 알리고 빈 사전을 돌려준다. 사전이
    없다고 판정을 멈출 이유는 없다. 빈 사전이면 프롬프트에서 anchored
    규칙만 빠진다. 다만 조용히 빠지면 판정 품질이 떨어진 이유를 나중에
    알 수 없으므로 반드시 알린다.
    """
    with uow:
        vocabulary = uow.ontology.get(
            workspace_id=workspace_id,
            ontology_id=CONTRACT_ID,
            version=version,
        )
    if vocabulary is None:
        print(
            f"경고: 어휘 스냅샷 {version}을 찾지 못했다. "
            "entity 종류 사전 없이(anchored 규칙 없이) 판정한다."
        )
        return ()
    return vocabulary.entity_type_entries


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-id", type=int, default=1)
    parser.add_argument(
        "--skip-judge",
        action="store_true",
        help="결정론 병합만 수행하고 LLM 판정을 건너뛴다.",
    )
    parser.add_argument(
        "--capacity",
        choices=[capacity.value for capacity in ModelCapacity],
        default=ModelCapacity.LARGE.value,
    )
    parser.add_argument(
        "--vocabulary-version",
        default=None,
        help=(
            "judge에 주입할 어휘 스냅샷 버전. 생략하면 최신 발행본을 고른다."
        ),
    )
    args = parser.parse_args()

    engine = create_engine(settings.sqlalchemy_database_url)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    uow = KnowledgeMaintenanceUnitOfWork(session_factory)

    judge = None
    name_embedder = None
    if not args.skip_judge:
        version = args.vocabulary_version
        if version is None:
            version = _resolve_vocabulary_version(
                uow,
                workspace_id=args.workspace_id,
            )
        entity_types: tuple[EntityTypeEntry, ...] = ()
        if version is None:
            print(
                "발행된 어휘 스냅샷이 없다. "
                "run_vocabulary_convergence_pipeline을 먼저 돌리면 "
                "entity 종류 사전이 판정에 주입된다. "
                "이번에는 사전 없이 판정한다."
            )
        else:
            entity_types = _load_entity_types(
                uow,
                workspace_id=args.workspace_id,
                version=version,
            )
            print(
                f"어휘 스냅샷 {version} entity 종류 "
                f"{len(entity_types)}종 주입"
            )
        service = get_llm_service(
            provider=LlmProvider.AWS_BEDROCK,
            model_capacity=ModelCapacity(args.capacity),
            streaming=False,
        )
        judge = BedrockIdentityJudge(
            service.get_llm(),
            entity_types=entity_types,
        )
        # 임베더를 못 만들면 여기서 멈춘다. 조용히 없이 돌면 후보군이
        # 정확 일치로 좁아져 표기가 조금 다른 같은 대상이 다시 각자
        # 노드로 굳는데, 그렇게 굳은 노드는 이 단계가 다시 합쳐 주지
        # 않는다.
        # 캐시를 둘러 이미 벡터로 바꿔 본 이름은 다시 임베딩하지 않는다.
        # 라운드마다 살아 있는 노드 별칭을 전부 다시 부르던 몫이 줄어든다.
        name_embedder = cached_name_embedder(
            EmbeddingServiceNameEmbedder(
                get_embedding_service(EmbeddingProvider.AWS_BEDROCK)
            ),
            SqlAlchemyNameEmbeddingCache(session_factory),
            workspace_id=args.workspace_id,
        )

    # kill switch를 읽는 자리는 이 러너 한 곳이다. 해소 서비스와 적용
    # 서비스는 설정을 직접 읽지 않고 넘겨받은 값만 본다.
    auto_merge_enabled = settings.KNOWLEDGE_AUTO_MERGE_ENABLED
    result = resolve_entity_candidates(
        workspace_id=args.workspace_id,
        judge=judge,
        uow=uow,
        name_embedder=name_embedder,
        auto_merge_enabled=auto_merge_enabled,
    )

    print("=== Resolution 결과 ===")
    print(
        f"  canonical 노드 발급 {result.nodes_created}"
        f"  | 후보 accepted {result.candidates_accepted}"
        f" · merged {result.candidates_merged}"
    )
    print(f"  단일 관찰 승격 {result.singletons_promoted}")
    print(
        f"  판정 그룹 {result.groups_judged}"
        f" (실패 {result.groups_failed})"
        f"  | proposal 생성 {result.proposals_created}"
        f" · 폐기 {result.proposals_abandoned}"
    )
    print(
        f"  유사 이름 블록 {result.blocks_formed}"
        f"  | 분할 판정 {result.blocks_judged}"
        f" (실패 {result.blocks_failed})"
        f"  | 병합 계류 {result.groups_abstained}"
    )

    if auto_merge_enabled:
        # 승인과 적용은 트랜잭션이 다르므로 안건마다 새 경계가 필요하다.
        def apply_uow() -> KnowledgeMaintenanceUnitOfWork:
            return KnowledgeMaintenanceUnitOfWork(
                session_factory,
                workspace_id=args.workspace_id,
            )

        applied = apply_mutation_proposals(
            apply_uow,
            workspace_id=args.workspace_id,
        )
        print("=== 자동 병합 적용 결과 ===")
        print(f"  적용된 안건 {applied.proposals_applied}")
        print(f"  실패한 안건 {applied.proposals_failed}")
        print(f"  새로 해소된 후보 {applied.candidates_resolved}")
        print(f"  기해소 스킵 {applied.candidates_already_resolved}")
    else:
        print(
            "자동 병합이 꺼져 있다(KNOWLEDGE_AUTO_MERGE_ENABLED=false). "
            "병합 안건은 계류로 남는다."
        )

    engine.dispose()


if __name__ == "__main__":
    main()
