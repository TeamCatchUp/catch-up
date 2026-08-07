"""저장된 Observation을 추출해 candidate로 남긴다.

`eval_llm_wiki_extraction.py`와 목적이 다르다. 저쪽은 파일을 읽어 결과를 파일로
떨구는 관찰 도구이고, 이 스크립트는 DB에 저장된 Observation을 읽어 DB에
candidate를 남긴다. 나중에 Dreaming Poller가 할 일을 손으로 돌려 보는 것이다.

LLM 호출은 transaction 밖에서 한다. 추출이 끝난 뒤에야 저장 transaction을
연다. 그렇지 않으면 LLM이 느린 동안 connection을 붙들게 된다.

아직 추출하지 않은 Observation만 고르므로 중간에 멈췄다 다시 돌려도 한 일을
되풀이하지 않는다.

실데이터 운용의 정본 경로는 사전 고정 + 수렴 러너다. 미고정(성장) 모드는
발행본이 없는 초기 상태의 관찰용으로만 남는다.

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
from typing import NamedTuple

import structlog
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from catchup.components.llm.constants import LlmProvider
from catchup.components.llm.constants import ModelCapacity
from catchup.components.llm.factory import get_llm_service
from catchup.configs.config import settings
from catchup.db.models import Observation as ObservationRow
from catchup.db.models import SourceVersion as SourceVersionRow
from catchup.evaluation.eval_llm_wiki_extraction import CONTRACT_VERSION
from catchup.evaluation.eval_llm_wiki_extraction import _grow_vocabulary
from catchup.evaluation.eval_llm_wiki_extraction import _harvest
from catchup.knowledge_maintenance.adapters.llm.structured_extractor import CONTRACT_ID
from catchup.knowledge_maintenance.adapters.llm.structured_extractor import (
    PROMPT_VERSION,
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
from catchup.knowledge_maintenance.domain.temporal import resolve_reference_time
from catchup.knowledge_maintenance.services.converge_vocabulary import (
    resolve_latest_published_version,
)
from catchup.knowledge_maintenance.services.store_knowledge_candidates import (
    record_failed_extraction,
)
from catchup.knowledge_maintenance.services.store_knowledge_candidates import (
    store_knowledge_candidates,
)

# 어휘를 만들기 전 단계에서는 스냅샷 이름이 없다. 비워 두는 대신 그 사실을
# 값으로 남겨야 실행이 어휘를 가리킬 수 있다.
UNVERSIONED_ONTOLOGY = "unversioned"

logger = structlog.get_logger(__name__)


class PendingEntry(NamedTuple):
    """추출을 기다리는 일 하나가 들고 다니는 재료다.

    기준 시각 사슬을 추출 시점에 계산하려면 Observation만으로는
    모자라 원문 버전의 시각이 함께 따라와야 한다.
    """

    event_id: int
    observation: StoredObservation
    source_updated_at: datetime | None
    observed_at: datetime


def _load_vocabulary(
    session_factory: Callable[[], Session],
    *,
    workspace_id: int,
    version: str | None,
) -> ExtractionVocabulary:
    """시작 어휘를 정한다.

    버전을 주지 않으면 빈 어휘에서 시작해 라운드마다 키운다. 주면 그
    스냅샷을 읽어 첫 라운드부터 사전을 프롬프트에 싣는다.
    """
    if version is None:
        return ExtractionVocabulary()
    with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
        found = uow.ontology.get(
            workspace_id=workspace_id,
            ontology_id=CONTRACT_ID,
            version=version,
        )
    if found is None:
        raise SystemExit(
            f"어휘 스냅샷을 찾을 수 없다: {CONTRACT_ID} {version}"
        )
    return found


def _next_vocabulary(
    current: ExtractionVocabulary,
    results: list[dict],
    *,
    round_index: int,
    pinned: bool,
) -> ExtractionVocabulary:
    """다음 라운드가 쓸 어휘를 정한다.

    버전을 고정한 실행은 어휘를 키우지 않는다. 이유가 둘이다. 첫째,
    한 버전 이름은 한 내용을 가리켜야 하므로 같은 이름에 라운드마다
    다른 내용을 담으면 스냅샷 저장이 충돌한다. 둘째, 사전을 들여온
    뒤의 새 이름은 자동으로 편입되는 것이 아니라 승격 절차를 거쳐야
    한다. 그래서 여기서는 승격 후보로 적어 두기만 한다.
    """
    if not pinned:
        return _grow_vocabulary(current, results, round_index)

    predicates, relation_types = _harvest(results)
    unknown_predicates = sorted(predicates - set(current.predicates))
    unknown_relations = sorted(relation_types - set(current.relation_types))
    reused = len(predicates) - len(unknown_predicates)
    if predicates:
        print(f"  사전 predicate 재사용 {reused}/{len(predicates)}")
    if unknown_predicates or unknown_relations:
        print(
            f"  승격 후보 (사전에 없어 이번 실행에는 싣지 않는다) — "
            f"predicate {unknown_predicates} / "
            f"relation {unknown_relations}"
        )
    return current


def _named(vocabulary: ExtractionVocabulary) -> ExtractionVocabulary:
    """이름 없는 어휘에 스냅샷 이름을 붙인다."""
    if vocabulary.snapshot_id:
        return vocabulary
    return vocabulary.model_copy(update={"snapshot_id": UNVERSIONED_ONTOLOGY})


async def _extract_one(
    extractor: StructuredKnowledgeExtractor,
    entry: PendingEntry,
    semaphore: asyncio.Semaphore,
    vocabulary: ExtractionVocabulary,
) -> dict:
    """Observation 하나를 추출한다. 실패해도 멈추지 않는다."""
    event_id, observation = entry.event_id, entry.observation
    reference_time, reference_time_source = resolve_reference_time(
        occurred_at=observation.observation.occurred_at,
        source_updated_at=entry.source_updated_at,
        observed_at=entry.observed_at,
    )
    # 어느 단계가 쓰였는지는 추출 품질을 되짚는 재료이자 감사 기록이다.
    logger.info(
        "extraction_reference_time_resolved",
        observation_id=str(observation.id),
        reference_time=reference_time.isoformat(),
        reference_time_source=reference_time_source,
    )
    request = KnowledgeExtractionRequest(
        content=observation.observation.content,
        source_type="channel_talk",
        metadata_entities=observation.observation.metadata_entities,
        vocabulary=vocabulary,
        reference_time=reference_time,
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
            "raw_output": diagnostics.raw_output,
        }

    return {
        "observation": observation,
        "event_id": event_id,
        "status": "ok",
        "batch": batch,
        "raw_output": diagnostics.raw_output,
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
        # 실패도 실행 기록으로 남긴다. 남기지 않으면 어느 Observation이 왜
        # 실패했는지 DB에 흔적이 없다.
        record_failed_extraction(
            observation,
            spec=spec,
            error=result.get("error") or result["status"],
            raw_output=result.get("raw_output"),
            uow=KnowledgeMaintenanceUnitOfWork(session_factory),
        )
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
        raw_output=result.get("raw_output"),
        uow=KnowledgeMaintenanceUnitOfWork(session_factory),
    )
    return {
        "key": str(observation.id)[:8],
        "event_id": result["event_id"],
        "status": "reused" if stored.reused else "stored",
        "entities": len(stored.batch.entity_ids),
        "claims": len(stored.batch.claim_ids),
        "relations": len(stored.batch.relation_ids),
        "located": stored.batch.located_claim_count,
        "not_found": stored.batch.demoted_not_found_count,
        "ambiguous": stored.batch.demoted_ambiguous_count,
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
    parser.add_argument(
        "--ontology-version",
        type=str,
        default=None,
        help=(
            "이 버전을 고정한다. 생략하면 최신 발행본을 자동 선택하고, "
            "발행본이 없으면 빈 어휘로 시작해 라운드마다 키운다."
        ),
    )
    args = parser.parse_args()

    engine = create_engine(settings.sqlalchemy_database_url)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

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
        read_timeout=120,
    )
    extractor = StructuredKnowledgeExtractor(service.get_llm())
    semaphore = asyncio.Semaphore(args.concurrency)
    resolved_version = args.ontology_version
    if resolved_version is None:
        with KnowledgeMaintenanceUnitOfWork(session_factory) as uow:
            resolved_version = resolve_latest_published_version(
                uow.ontology.list_versions(
                    workspace_id=args.workspace_id,
                    ontology_id=CONTRACT_ID,
                )
            )
        if resolved_version is not None:
            print(f"최신 발행 어휘 {resolved_version}을 자동 선택했다.")
    pinned = resolved_version is not None
    vocabulary = _load_vocabulary(
        session_factory,
        workspace_id=args.workspace_id,
        version=resolved_version,
    )

    print(
        f"Observation {len(pending)}건, 라운드 {args.round_size}건씩, "
        f"동시 {args.concurrency}건, 모델 {args.capacity}"
    )
    if pinned:
        print(
            f"어휘 {vocabulary.snapshot_id} 고정 — "
            f"predicate {len(vocabulary.predicates)}종"
            f" (정의 {len(vocabulary.predicate_entries)}종),"
            f" relation {len(vocabulary.relation_types)}종"
            f" (정의 {len(vocabulary.relation_type_entries)}종)."
            f" 새 이름은 승격 후보로만 남긴다."
        )

    summary = {"stored": 0, "reused": 0, "error": 0, "contract_violation": 0}
    totals = {
        "entities": 0,
        "claims": 0,
        "relations": 0,
        "located": 0,
        "not_found": 0,
        "ambiguous": 0,
    }

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
            prompt_version=PROMPT_VERSION,
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

        vocabulary = _next_vocabulary(
            vocabulary,
            _harvest_shape(list(results)),
            round_index=number,
            pinned=pinned,
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
    # 인용 검증 결과다. reused 실행은 집계에 없으므로 이 수치는 이번에
    # 새로 저장한 run만의 것이다. not_found가 높으면 환각이나 프롬프트
    # 문제, ambiguous가 높으면 본문 중복이 원인이다.
    demoted = totals["not_found"] + totals["ambiguous"]
    checked = totals["located"] + demoted
    if checked:
        rate = demoted / checked * 100
        print(
            f"  claim 인용 (새로 저장한 run 기준) — "
            f"위치 확정 {totals['located']}"
            f"  강등 {demoted} ({rate:.1f}%"
            f" · 본문에 없음 {totals['not_found']}"
            f" · 여러 번 나옴 {totals['ambiguous']})"
        )
    print(f"  끝난 시각 {datetime.now(timezone.utc).isoformat()}")

    engine.dispose()


def _observation_of(
    event: PipelineEvent,
    uow: KnowledgeMaintenanceUnitOfWork,
    workspace_id: int,
) -> PendingEntry | None:
    """큐의 일이 가리키는 Observation과 원문 시각을 읽는다.

    기준 시각 사슬의 아래 두 단계(원문 변경 시각·수집 시각)는
    Observation이 아니라 그 바탕이 된 SourceVersion에 있으므로 함께
    읽어 둔다.

    `fk_observations_source_version`이 존재를 보장하고
    `observed_at`은 NOT NULL이므로, Observation이 있는데 SourceVersion을
    못 찾는 것은 스키마 손상 신호다. 다른 시각으로 메우지 않고 이
    건을 건너뛰며 소리를 낸다 — 사슬에 없는 단계를 몰래 끼워 넣으면
    기준 시각의 출처가 거짓이 된다.
    """
    session = uow.observations._session  # noqa: SLF001
    row = session.get(ObservationRow, event.aggregate_id)
    if row is None:
        return None
    version = session.get(SourceVersionRow, row.source_version_id)
    if version is None:
        logger.error(
            "extraction_source_version_missing",
            observation_id=str(row.id),
            source_version_id=str(row.source_version_id),
        )
        return None
    return PendingEntry(
        event_id=event.id,
        observation=observation_to_domain(row),
        source_updated_at=version.source_updated_at,
        observed_at=version.observed_at,
    )


def _settle(
    record: dict,
    *,
    session_factory: Callable[[], Session],
) -> None:
    """처리 결과를 큐에 되돌린다.

    실패 종류마다 봐주는 횟수가 다르다. 계약 위반은 흔들림일 수 있어 몇 번
    더 해보되 적게, API 오류는 오래 갈 수 있어 더 많이 봐준다.
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
                FailureKind.CONTRACT_VIOLATION
                if record["status"] == "contract_violation"
                else FailureKind.API_ERROR
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
