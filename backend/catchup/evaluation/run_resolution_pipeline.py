"""pending entity 후보를 canonical identity로 해소한다.

`run_extraction_pipeline.py`의 다음 단계다. 저쪽이 Observation에서 후보를
뽑는다면, 이 스크립트는 쌓인 후보를 결정론 병합(즉시 적용)과 같은 이름
그룹 LLM 판정(proposal)으로 해소한다. 행 2 Resolution의 첫 슬라이스를
손으로 돌려 보는 것이다.

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

from catchup.components.llm.constants import LlmProvider
from catchup.components.llm.constants import ModelCapacity
from catchup.components.llm.factory import get_llm_service
from catchup.configs.config import settings
from catchup.knowledge_maintenance.adapters.llm.identity_judge import (
    BedrockIdentityJudge,
)
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)
from catchup.knowledge_maintenance.services.resolve_entity_candidates import (
    resolve_entity_candidates,
)


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
    args = parser.parse_args()

    judge = None
    if not args.skip_judge:
        service = get_llm_service(
            provider=LlmProvider.AWS_BEDROCK,
            model_capacity=ModelCapacity(args.capacity),
            streaming=False,
        )
        judge = BedrockIdentityJudge(service.get_llm())

    engine = create_engine(settings.sqlalchemy_database_url)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    result = resolve_entity_candidates(
        workspace_id=args.workspace_id,
        judge=judge,
        uow=KnowledgeMaintenanceUnitOfWork(session_factory),
    )

    print("=== Resolution 결과 ===")
    print(
        f"  canonical 노드 발급 {result.nodes_created}"
        f"  | 후보 accepted {result.candidates_accepted}"
        f" · merged {result.candidates_merged}"
    )
    print(
        f"  판정 그룹 {result.groups_judged}"
        f" (실패 {result.groups_failed})"
        f"  | proposal 생성 {result.proposals_created}"
        f" · 폐기 {result.proposals_abandoned}"
    )

    engine.dispose()


if __name__ == "__main__":
    main()
