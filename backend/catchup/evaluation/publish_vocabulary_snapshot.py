"""검토를 마친 어휘 사전 JSON을 스냅샷으로 발행한다.

소급 정의 부트스트랩(1회성, 개발 한정)이며 운영의 정상 경로는 승격 절차다.
같은 버전에 다른 내용을 다시 발행하려 하면 OntologySnapshotConflict로
거부된다. 사전은 덮어쓰지 않는다.

실행:
    uv run python -m catchup.evaluation.publish_vocabulary_snapshot \
        --input catchup/evaluation/data/vocabulary_v2.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from catchup.configs.config import settings
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)
from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary

ONTOLOGY_ID = "catchup.knowledge_candidates"
DEFAULT_INPUT = Path(__file__).parent / "data" / "vocabulary_v2.json"


def main() -> None:
    """JSON을 읽어 어휘 스냅샷으로 발행한다."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-id", type=int, default=1)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    args = parser.parse_args()

    vocabulary = ExtractionVocabulary.model_validate(
        json.loads(args.input.read_text(encoding="utf-8"))
    )

    engine = create_engine(settings.sqlalchemy_database_url)
    uow = KnowledgeMaintenanceUnitOfWork(
        sessionmaker(bind=engine, expire_on_commit=False)
    )
    with uow:
        stored = uow.ontology.ensure(
            workspace_id=args.workspace_id,
            ontology_id=ONTOLOGY_ID,
            vocabulary=vocabulary,
        )
        uow.commit()

    print(
        f"발행: version {stored.snapshot_id} — "
        f"entity_type {len(stored.entity_type_entries)}종 · "
        f"predicate {len(stored.predicate_entries)}종 · "
        f"relation {len(stored.relation_type_entries)}종"
    )


if __name__ == "__main__":
    main()
