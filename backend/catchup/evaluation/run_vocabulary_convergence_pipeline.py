"""사전 밖 predicate·relation을 수렴해 어휘 스냅샷 새 버전을 발행한다.

사람은 이 루프에 개입하지 않는다. 어휘는 지식이 아니라 추출의 렌즈이고,
지식의 진실성 게이트는 하류의 artifact 검수에 그대로 있다. 사람 검토의
자리는 기계 가드(스키마 검증·관측 증거·enum 치역·단조 증가)가 대신한다.

발행은 전량 검증 후 단일 ensure다. 신규 항목이 없으면 버전을 만들지
않으므로 여러 번 돌려도 안전하다. 발행 뒤에는 재추출을 돌려야 수렴이
실체화된다(사전 변경 = 추출 계약 변경).

개발과 평가 전용이다.

실행:
    uv run python -m catchup.evaluation.run_vocabulary_convergence_pipeline
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime
from datetime import timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from catchup.components.llm.constants import LlmProvider
from catchup.components.llm.constants import ModelCapacity
from catchup.components.llm.factory import get_llm_service
from catchup.configs.config import settings
from catchup.knowledge_maintenance.adapters.llm.structured_extractor import CONTRACT_ID
from catchup.knowledge_maintenance.adapters.llm.vocabulary_converger import (
    LlmVocabularyConverger,
)
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)
from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary
from catchup.knowledge_maintenance.services.converge_vocabulary import guard_convergence
from catchup.knowledge_maintenance.services.converge_vocabulary import (
    normalize_vocabulary_name,
)
from catchup.knowledge_maintenance.services.converge_vocabulary import (
    publish_converged_vocabulary,
)
from catchup.knowledge_maintenance.services.converge_vocabulary import (
    resolve_latest_published_version,
)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-id", type=int, default=1)
    parser.add_argument(
        "--capacity",
        choices=[capacity.value for capacity in ModelCapacity],
        default=ModelCapacity.LARGE.value,
    )
    parser.add_argument(
        "--ontology-version",
        default=None,
        help="수렴의 기준 사전 버전. 없으면 최신 발행본을 고른다.",
    )
    args = parser.parse_args()

    engine = create_engine(settings.sqlalchemy_database_url)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    # 1. 현행 사전과 사용 현황을 읽는다. LLM 호출 전에 transaction을 닫는다.
    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        versions = uow.ontology.list_versions(
            workspace_id=args.workspace_id, ontology_id=CONTRACT_ID
        )
        version = args.ontology_version or resolve_latest_published_version(
            versions
        )
        current = ExtractionVocabulary()
        if version is not None:
            found = uow.ontology.get(
                workspace_id=args.workspace_id,
                ontology_id=CONTRACT_ID,
                version=version,
            )
            if found is None:
                raise SystemExit(f"어휘 스냅샷을 찾을 수 없다: {version}")
            current = found
        predicate_usage = uow.knowledge_candidates.summarize_predicate_usage(
            workspace_id=args.workspace_id
        )
        relation_usage = uow.knowledge_candidates.summarize_relation_usage(
            workspace_id=args.workspace_id
        )

    known_predicates = set(current.predicates)
    known_relations = set(current.relation_types)
    oov_predicates = [
        item for item in predicate_usage if item.name not in known_predicates
    ]
    oov_relations = [
        item for item in relation_usage if item.name not in known_relations
    ]
    print(
        f"기준 사전 {current.snapshot_id or '(없음)'} — "
        f"OOV predicate {len(oov_predicates)}종 · "
        f"relation {len(oov_relations)}종"
    )
    if not oov_predicates and not oov_relations:
        print("수렴할 것이 없다.")
        engine.dispose()
        return

    # 2. LLM 수렴 판단.
    service = get_llm_service(
        provider=LlmProvider.AWS_BEDROCK,
        model_capacity=ModelCapacity(args.capacity),
        streaming=False,
        read_timeout=120,
    )
    converger = LlmVocabularyConverger(service.get_llm())
    proposal = await converger.propose(
        current=current,
        predicate_usage=oov_predicates,
        relation_usage=oov_relations,
    )
    if proposal is None:
        print("LLM 수렴 판단이 실패했다. 이번 라운드는 발행 없이 끝낸다.")
        engine.dispose()
        return

    # 3. 기계 가드 → 발행.
    guarded = guard_convergence(
        proposal,
        current=current,
        predicate_usage=oov_predicates,
        relation_usage=oov_relations,
    )
    outcome = publish_converged_vocabulary(
        guarded,
        workspace_id=args.workspace_id,
        ontology_id=CONTRACT_ID,
        current=current,
        uow=KnowledgeMaintenanceUnitOfWork(session_factory),
    )

    print("=== 어휘 수렴 결과 ===")
    for absorption in guarded.absorptions:
        print(
            f"  흡수: {absorption.candidate_name} → "
            f"{absorption.canonical_name} ({absorption.reason})"
        )
    for rejection in guarded.rejections:
        print(f"  기각: {rejection.name} — {rejection.reason}")
    if outcome.version is None:
        print("  신규 항목이 없어 발행하지 않았다.")
    else:
        print(
            f"  발행: {outcome.version} — "
            f"predicate +{len(outcome.added_predicates)} "
            f"{list(outcome.added_predicates)} · "
            f"relation +{len(outcome.added_relations)}"
        )
        print("  재추출을 돌려야 수렴이 실체화된다.")

    # 잔여 OOV: 이번에 entry로도 흡수로도 안 덮인 이름. 다음 라운드나
    # 프롬프트 개선의 재료다.
    covered = set(guarded.covered_names)
    remaining = [
        item.name
        for item in list(oov_predicates) + list(oov_relations)
        if item.name not in covered
        and normalize_vocabulary_name(item.name) not in covered
    ]
    if remaining:
        print(f"  잔여 OOV {len(remaining)}종: {remaining}")
    print(f"  끝난 시각 {datetime.now(timezone.utc).isoformat()}")

    engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
