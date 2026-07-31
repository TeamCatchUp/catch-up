"""승인된 병합 안건의 결정 저널을 적용한다.

`review_merge_proposals`가 남긴 approved 안건을 읽어 canonical 노드를
만들고 후보를 해소한다. 결정은 이미 끝났으므로 여기서는 아무것도 묻지
않는다. 재실행은 무동작이다 — applied 안건은 다시 집지 않는다.

개발과 평가 전용이다.

실행:
    uv run python -m catchup.evaluation.run_mutation_apply_pipeline
"""

from __future__ import annotations

import argparse

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from catchup.configs.config import settings
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)
from catchup.knowledge_maintenance.services.apply_mutation_proposals import (
    apply_mutation_proposals,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-id", type=int, default=1)
    args = parser.parse_args()

    engine = create_engine(settings.sqlalchemy_database_url)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    def uow() -> KnowledgeMaintenanceUnitOfWork:
        return KnowledgeMaintenanceUnitOfWork(
            session_factory, workspace_id=args.workspace_id
        )

    result = apply_mutation_proposals(uow, workspace_id=args.workspace_id)

    print("=== 병합 적용 결과 ===")
    print(f"  적용된 안건 {result.proposals_applied}")
    print(f"  실패한 안건 {result.proposals_failed}")
    print(f"  새로 해소된 후보 {result.candidates_resolved}")
    print(f"  기해소 스킵 {result.candidates_already_resolved}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
