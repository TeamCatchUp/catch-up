"""저장된 Observation을 추출해 candidate로 남긴다.

`eval_llm_wiki_extraction.py`와 목적이 다르다. 저쪽은 파일을 읽어 결과를 파일로
떨구는 관찰 도구이고, 이 스크립트는 DB에 저장된 Observation을 읽어 DB에
candidate를 남긴다. 나중에 Dreaming Poller가 할 일을 손으로 돌려 보는 것이다.

LLM 호출은 transaction 밖에서 한다. 추출이 끝난 뒤에야 저장 transaction을
연다. 그렇지 않으면 LLM이 느린 동안 connection을 붙들게 된다.

아직 추출하지 않은 Observation만 고르므로 중간에 멈췄다 다시 돌려도 한 일을
되풀이하지 않는다.

개발과 평가 전용이다.

실행:
    uv run python -m catchup.evaluation.run_extraction_pipeline --limit 3
"""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Callable
from datetime import datetime
from datetime import timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from catchup.components.llm.constants import LlmProvider
from catchup.components.llm.constants import ModelCapacity
from catchup.components.llm.factory import get_llm_service
from catchup.configs.config import settings
from catchup.db.models import Observation as ObservationRow
from catchup.evaluation.eval_llm_wiki_extraction import CONTRACT_VERSION
from catchup.evaluation.eval_llm_wiki_extraction import _grow_vocabulary
from catchup.knowledge_maintenance.adapters.llm.structured_extractor import CONTRACT_ID
from catchup.knowledge_maintenance.adapters.llm.structured_extractor import (
    TEMPLATE_PATH,
)
from catchup.knowledge_maintenance.adapters.llm.structured_extractor import (
    StructuredKnowledgeExtractor,
)
from catchup.knowledge_maintenance.adapters.postgres.mappers import (
    observation_to_domain,
)
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)
from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary
from catchup.knowledge_maintenance.contracts.extraction import (
    KnowledgeExtractionRequest,
)
from catchup.knowledge_maintenance.domain.knowledge_candidate import ExtractionRunSpec
from catchup.knowledge_maintenance.domain.observation import StoredObservation
from catchup.knowledge_maintenance.domain.pipeline_event import FailureKind
from catchup.knowledge_maintenance.domain.pipeline_event import PipelineEvent
from catchup.knowledge_maintenance.domain.pipeline_event import PipelineEventStatus
from catchup.knowledge_maintenance.domain.pipeline_event import PipelineEventType
from catchup.knowledge_maintenance.services.store_knowledge_candidates import (
    store_knowledge_candidates,
)

# 어휘를 만들기 전 단계에서는 스냅샷 이름이 없다. 비워 두는 대신 그 사실을
# 값으로 남겨야 실행이 어휘를 가리킬 수 있다.
UNVERSIONED_ONTOLOGY = "unversioned"


def _named(vocabulary: ExtractionVocabulary) -> ExtractionVocabulary:
    """이름 없는 어휘에 스냅샷 이름을 붙인다."""
    if vocabulary.snapshot_id:
        return vocabulary
    return vocabulary.model_copy(update={"snapshot_id": UNVERSIONED_ONTOLOGY})


async def _extract_one(
    extractor: StructuredKnowledgeExtractor,
    entry: tuple[int, StoredObservation],
    semaphore: asyncio.Semaphore,
    vocabulary: ExtractionVocabulary,
) -> dict:
    """Observation 하나를 추출한다. 실패해도 멈추지 않는다."""
    event_id, observation = entry
    request = KnowledgeExtractionRequest(
        content=observation.observation.content,
        source_type="channel_talk",
        metadata_entities=observation.observation.metadata_entities,
        vocabulary=vocabulary,
        contract_version=CONTRACT_VERSION,
    )

    async with semaphore:
        try:
            batch, diagnostics = await extractor.extract_with_diagnostics(request)
        except Exception as error:
            return {
                "observation": observation,
                "event_id": event_id,
                "status": "error",
                "error": f"{type(error).__name__}: {error}",
            }

    if batch is None:
        return {
            "observation": observation,
            "event_id": event_id,
            "status": "contract_violation",
            "error": diagnostics.parse_error,
        }

    return {
        "observation": observation,
        "event_id": event_id,
        "status": "ok",
        "batch": batch,
    }


def _harvest_shape(results: list[dict]) -> list[dict]:
    """어휘 갱신 함수가 읽는 형태로 맞춘다.

    `_grow_vocabulary`는 관찰 러너의 JSON 결과를 받도록 만들어졌으므로
    같은 모양으로 변환해 재사용한다.
    """
    shaped: list[dict] = []
    for result in results:
        if result["status"] != "ok":
            shaped.append({"status": result["status"]})
            continue
        shaped.append(
            {
                "status": "ok",
                "batch": result["batch"].model_dump(mode="json"),
            }
        )
    return shaped


def _store(
    result: dict,
    *,
    spec: ExtractionRunSpec,
    session_factory: Callable[[], Session],
) -> dict:
    """추출 결과를 candidate로 남긴다."""
    observation: StoredObservation = result["observation"]
    if result["status"] != "ok":
        return {
            "key": str(observation.id)[:8],
            "event_id": result["event_id"],
            "status": result["status"],
            "error": result.get("error") or "",
        }

    stored = store_knowledge_candidates(
        observation,
        result["batch"],
        spec=spec,
        uow=KnowledgeMaintenanceUnitOfWork(session_factory),
    )
    return {
        "key": str(observation.id)[:8],
        "event_id": result["event_id"],
        "status": "reused" if stored.reused else "stored",
        "entities": len(stored.batch.entity_ids),
        "claims": len(stored.batch.claim_ids),
        "relations": len(stored.batch.relation_ids),
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-id", type=int, default=1)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--round-size", type=int, default=6)
    parser.add_argument(
        "--capacity",
        choices=[capacity.value for capacity in ModelCapacity],
        default=ModelCapacity.LARGE.value,
    )
    args = parser.parse_args()

    engine = create_engine(settings.sqlalchemy_database_url)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        # 큐를 도입하기 전에 저장된 Observation에는 지시가 없다. 채워 둔다.
        backfilled = uow.pipeline_events.backfill_missing(
            workspace_id=args.workspace_id,
            event_type=PipelineEventType.OBSERVATION_READY,
        )
        uow.commit()
    if backfilled:
        print(f"큐에 없던 Observation {backfilled}건을 채웠다.")

    # 시각은 백필 뒤에 읽는다. 먼저 읽으면 방금 넣은 일의 available_at이
    # 그보다 뒤라 아직 오지 않은 것으로 보인다.
    now = datetime.now(timezone.utc)
    with KnowledgeMaintenanceUnitOfWork(session_factory) as reader:
        events = reader.pipeline_events.claim_pending(
            workspace_id=args.workspace_id,
            event_type=PipelineEventType.OBSERVATION_READY,
            now=now,
            limit=args.limit,
        )
        pending = [
            item
            for item in (
                _observation_of(event, reader, args.workspace_id)
                for event in events
            )
            if item is not None
        ]

    if not pending:
        print("처리할 일이 없다.")
        engine.dispose()
        return

    service = get_llm_service(
        provider=LlmProvider.AWS_BEDROCK,
        model_capacity=ModelCapacity(args.capacity),
        streaming=False,
    )
    extractor = StructuredKnowledgeExtractor(service.get_llm())
    semaphore = asyncio.Semaphore(args.concurrency)
    vocabulary = ExtractionVocabulary()

    print(
        f"Observation {len(pending)}건, 라운드 {args.round_size}건씩, "
        f"동시 {args.concurrency}건, 모델 {args.capacity}"
    )

    summary = {"stored": 0, "reused": 0, "error": 0, "contract_violation": 0}
    totals = {"entities": 0, "claims": 0, "relations": 0}

    for offset in range(0, len(pending), args.round_size):
        chunk = pending[offset : offset + args.round_size]
        number = offset // args.round_size + 1
        print(f"\nround {number} ({len(chunk)}건)")

        results = await asyncio.gather(
            *(
                _extract_one(extractor, entry, semaphore, vocabulary)
                for entry in chunk
            )
        )

        # 어휘 스냅샷은 이 라운드가 무엇을 보고 뽑았는지를 가리킨다. 저장
        # 서비스가 이 목록을 행으로 남기므로 나중에 되짚을 수 있다.
        spec = ExtractionRunSpec(
            provider=LlmProvider.AWS_BEDROCK.value,
            extractor_version=f"{CONTRACT_ID}/{CONTRACT_VERSION}",
            ontology_id=CONTRACT_ID,
            vocabulary=_named(vocabulary),
            model=args.capacity,
            prompt_version=TEMPLATE_PATH,
        )

        for result in results:
            record = _store(
                result,
                spec=spec,
                session_factory=session_factory,
            )
            _settle(record, session_factory=session_factory)
            summary[record["status"]] = summary.get(record["status"], 0) + 1
            for key in totals:
                totals[key] += record.get(key, 0)
            detail = (
                f"entity {record['entities']:2d} "
                f"claim {record['claims']:2d} "
                f"relation {record['relations']:2d}"
                if record["status"] == "stored"
                else record["status"]
            )
            print(f"  {record['key']}  {detail}")

        vocabulary = _grow_vocabulary(
            vocabulary,
            _harvest_shape(list(results)),
            number,
        )

    print("\n=== 저장 결과 ===")
    for key, count in summary.items():
        if count:
            print(f"  {key}: {count}")
    print(
        f"  candidate — entity {totals['entities']}"
        f"  claim {totals['claims']}"
        f"  relation {totals['relations']}"
    )
    print(f"  끝난 시각 {datetime.now(timezone.utc).isoformat()}")

    engine.dispose()


def _observation_of(
    event: PipelineEvent,
    uow: KnowledgeMaintenanceUnitOfWork,
    workspace_id: int,
) -> tuple[int, StoredObservation] | None:
    """큐의 일이 가리키는 Observation을 읽는다."""
    session = uow.observations._session  # noqa: SLF001
    row = session.get(ObservationRow, event.aggregate_id)
    if row is None:
        return None
    return event.id, observation_to_domain(row)


def _settle(
    record: dict,
    *,
    session_factory: Callable[[], Session],
) -> None:
    """처리 결과를 큐에 되돌린다.

    계약 위반은 같은 입력에 같은 계약이면 다시 해도 같으므로 접는다.
    API 오류는 시간이 지나면 풀리므로 물러났다가 다시 나타난다.
    """
    now = datetime.now(timezone.utc)
    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        if record["status"] in ("stored", "reused"):
            uow.pipeline_events.mark_processed(
                event_id=record["event_id"],
                now=now,
            )
        else:
            kind = (
                FailureKind.PERMANENT
                if record["status"] == "contract_violation"
                else FailureKind.TRANSIENT
            )
            settled = uow.pipeline_events.mark_failed(
                event_id=record["event_id"],
                kind=kind,
                error=record.get("error") or record["status"],
                now=now,
            )
            record["retry_at"] = (
                settled.available_at
                if settled.status is PipelineEventStatus.PENDING
                else None
            )
        uow.commit()


if __name__ == "__main__":
    asyncio.run(main())
