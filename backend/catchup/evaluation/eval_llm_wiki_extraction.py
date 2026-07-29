"""평가 원문으로 Extraction을 한 번 돌려 관찰한다.

평가가 아니라 관찰이 목적이다. 정답과 대조하지 않고, 어휘 제약 없이
자유 추출해서 무엇이 나오는지 본다. 보려는 것은 세 가지이다.

1. Claim이 'subject + predicate + value'로 떨어지는가
2. 어떤 predicate가 실제로 나오는가
3. 계약을 위반하는 출력이 얼마나 되는가

원문은 jira·slack·github·confluence의 트러블슈팅 기록이라 ChannelTalk
상담과 어휘가 다르다. 여기서 나온 predicate를 그대로 어휘 v1으로 쓰지
않는다. 이 실행의 목적은 계약이 성립하는지 확인하는 데 있다.

실행:
    uv run python -m catchup.evaluation.eval_llm_wiki_extraction --limit 3
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from datetime import datetime
from datetime import timezone
from pathlib import Path

from catchup.components.llm.constants import LlmProvider
from catchup.components.llm.constants import ModelCapacity
from catchup.components.llm.factory import get_llm_service
from catchup.evaluation.channel_talk_extraction_dataset import ChannelTalkDatasetMode
from catchup.evaluation.channel_talk_extraction_dataset import load_channel_talk_sources
from catchup.evaluation.llm_wiki_extraction_dataset import ExtractionSource
from catchup.evaluation.llm_wiki_extraction_dataset import load_extraction_sources
from catchup.knowledge_maintenance.adapters.llm.structured_extractor import (
    StructuredKnowledgeExtractor,
)
from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary
from catchup.knowledge_maintenance.contracts.extraction import (
    KnowledgeExtractionRequest,
)

CONTRACT_VERSION = "0"
DEFAULT_OUTPUT_DIR = (
    Path(__file__).parent.parent / "experiments" / "llm_wiki_extraction" / "output"
)

LLM_WIKI_DATASET = "llm_wiki"
CHANNEL_TALK_RAW_DATASET = "channel_talk_raw"
CHANNEL_TALK_NORMALIZED_DATASET = "channel_talk_normalized"

# 이 값들은 원문에 구조로 이미 적혀 있으므로 추출이 지식으로 만들면 안 된다.
# `source_attributes`에서 걷어 정답으로 쓴다.
_SOURCE_FIELD_KEYS = ("title", "state", "priority")
_SOURCE_FIELD_LIST_KEYS = ("tags", "buttons")


def _load_sources(dataset: str) -> tuple[ExtractionSource, ...]:
    """고른 데이터셋을 읽는다."""
    if dataset == LLM_WIKI_DATASET:
        return load_extraction_sources()
    if dataset == CHANNEL_TALK_RAW_DATASET:
        return load_channel_talk_sources(ChannelTalkDatasetMode.RAW)
    return load_channel_talk_sources(ChannelTalkDatasetMode.NORMALIZED)


def _source_field_values(source: ExtractionSource) -> set[str]:
    """원문이 구조로 들고 있던 값을 모은다.

    레이어 1을 통과하지 않은 데이터셋에는 `source_attributes`가 비어 있으므로,
    같은 key의 정규화 결과에서 정답을 가져와야 두 형태를 같은 잣대로 잰다.
    """
    attributes = source.observation.source_attributes
    values: set[str] = set()

    for key in _SOURCE_FIELD_KEYS:
        value = attributes.get(key)
        if isinstance(value, str) and value.strip():
            values.add(_fold(value))

    for key in _SOURCE_FIELD_LIST_KEYS:
        for item in attributes.get(key) or ():
            if isinstance(item, str) and item.strip():
                values.add(_fold(item))

    for entry in attributes.get("lifecycle") or ():
        if isinstance(entry, dict) and isinstance(entry.get("action"), str):
            values.add(_fold(entry["action"]))

    for entry in attributes.get("attachments") or ():
        if isinstance(entry, dict) and isinstance(entry.get("name"), str):
            values.add(_fold(entry["name"]))

    for entity in source.observation.metadata_entities:
        values.add(_fold(entity.display_name))

    return values


def _fold(value: str) -> str:
    """비교할 수 있게 공백과 대소문자를 고른다."""
    return " ".join(value.split()).casefold()


def _build_source_field_index(dataset: str) -> dict[str, set[str]]:
    """원문 key마다 걷어냈어야 할 값의 집합을 만든다.

    정답은 언제나 정규화된 쪽에서 가져온다. raw 형태는 그 값들이 본문 텍스트에
    섞여 있을 뿐 구조로는 없기 때문에, 스스로는 정답을 댈 수 없다.
    """
    if dataset == LLM_WIKI_DATASET:
        return {}
    return {
        source.key: _source_field_values(source)
        for source in load_channel_talk_sources(ChannelTalkDatasetMode.NORMALIZED)
    }


def _report_source_field_leakage(
    results: list[dict],
    field_index: dict[str, set[str]],
) -> None:
    """추출이 원문 구조를 지식으로 착각한 정도를 잰다."""
    if not field_index:
        return

    total = 0
    leaked = 0
    leaked_predicates: Counter[str] = Counter()

    for result in results:
        if result["status"] != "ok":
            continue
        expected = field_index.get(result["key"])
        if expected is None:
            continue
        for claim in result["batch"]["claims"]:
            total += 1
            value = claim["value"]
            if not isinstance(value, str):
                continue
            if _fold(value) in expected:
                leaked += 1
                leaked_predicates[claim["predicate"]] += 1

    print("\n=== 소스 필드 누출 ===")
    if total == 0:
        print("  claim이 없다")
        return
    print(f"  {leaked}/{total} ({leaked / total:.1%})")
    for predicate, count in leaked_predicates.most_common(10):
        print(f"    {count:3d}  {predicate}")


async def _extract_one(
    extractor: StructuredKnowledgeExtractor,
    source: ExtractionSource,
    semaphore: asyncio.Semaphore,
    vocabulary: ExtractionVocabulary,
) -> dict:
    """원문 한 건을 추출하고 실패해도 결과를 남긴다."""
    request = KnowledgeExtractionRequest(
        content=source.observation.content,
        source_type=source.source_type,
        metadata_entities=source.observation.metadata_entities,
        vocabulary=vocabulary,
        contract_version=CONTRACT_VERSION,
    )

    async with semaphore:
        try:
            batch, diagnostics = await extractor.extract_with_diagnostics(request)
        except Exception as error:  # 관찰이 목적이므로 한 건 실패로 멈추지 않는다.
            return {
                "key": source.key,
                "document_id": source.document_id,
                "source_type": source.source_type,
                "cluster_id": source.cluster_id,
                "status": "error",
                "error": f"{type(error).__name__}: {error}",
            }

    if batch is None:
        return {
            "key": source.key,
            "document_id": source.document_id,
            "source_type": source.source_type,
            "cluster_id": source.cluster_id,
            "status": "contract_violation",
            "error": diagnostics.parse_error,
            "raw_output": diagnostics.raw_output,
        }

    return {
        "key": source.key,
        "document_id": source.document_id,
        "source_type": source.source_type,
        "cluster_id": source.cluster_id,
        "status": "ok",
        "batch": batch.model_dump(mode="json"),
    }


def _harvest(results: list[dict]) -> tuple[set[str], set[str]]:
    """이번 라운드가 실제로 쓴 어휘를 걷는다."""
    predicates: set[str] = set()
    relation_types: set[str] = set()
    for result in results:
        if result["status"] != "ok":
            continue
        batch = result["batch"]
        predicates.update(claim["predicate"] for claim in batch["claims"])
        relation_types.update(
            relation["relation_type"] for relation in batch["relation_assertions"]
        )
    return predicates, relation_types


def _grow_vocabulary(
    current: ExtractionVocabulary,
    results: list[dict],
    round_index: int,
) -> ExtractionVocabulary:
    """라운드 경계에서만 어휘를 넓힌다.

    추출 도중에 넓히면 같은 라운드의 다른 문서가 그것을 볼지 말지가
    스케줄링 순서에 달리게 되어 실행할 때마다 결과가 달라진다.
    """
    predicates, relation_types = _harvest(results)
    added_predicates = predicates - set(current.predicates)
    added_relations = relation_types - set(current.relation_types)

    print(
        f"  어휘 predicate +{len(added_predicates)}"
        f" (총 {len(current.predicates) + len(added_predicates)})"
        f" / relation +{len(added_relations)}"
        f" (총 {len(current.relation_types) + len(added_relations)})"
    )
    reused = len(predicates) - len(added_predicates)
    if predicates:
        print(f"  이번 라운드 predicate 재사용 {reused}/{len(predicates)}")

    return ExtractionVocabulary(
        snapshot_id=f"round-{round_index}",
        predicates=tuple(sorted(set(current.predicates) | predicates)),
        relation_types=tuple(sorted(set(current.relation_types) | relation_types)),
    )


def _summarize(results: list[dict]) -> None:
    """관찰하려던 세 가지를 콘솔에 낸다."""
    statuses = Counter(result["status"] for result in results)
    print("\n=== 상태 ===")
    for status, count in statuses.most_common():
        print(f"  {status}: {count}")

    predicates: Counter[str] = Counter()
    relation_types: Counter[str] = Counter()
    entity_types: Counter[str] = Counter()
    value_types: Counter[str] = Counter()
    empty_documents = 0

    for result in results:
        if result["status"] != "ok":
            continue
        batch = result["batch"]
        if not (batch["entities"] or batch["claims"] or batch["relation_assertions"]):
            empty_documents += 1
        for entity in batch["entities"]:
            entity_types[entity["proposed_type"]] += 1
        for claim in batch["claims"]:
            predicates[claim["predicate"]] += 1
            value_types[claim["value_type"]] += 1
        for relation in batch["relation_assertions"]:
            relation_types[relation["relation_type"]] += 1

    print("\n=== 규모 ===")
    print(f"  entity: {sum(entity_types.values())}")
    print(f"  claim: {sum(predicates.values())}")
    print(f"  relation: {sum(relation_types.values())}")
    print(f"  아무것도 안 나온 문서: {empty_documents}")

    print(f"\n=== predicate ({len(predicates)}종) ===")
    for predicate, count in predicates.most_common():
        print(f"  {count:3d}  {predicate}")

    print(f"\n=== relation_type ({len(relation_types)}종) ===")
    for relation_type, count in relation_types.most_common(20):
        print(f"  {count:3d}  {relation_type}")

    print(f"\n=== entity_type ({len(entity_types)}종) ===")
    for entity_type, count in entity_types.most_common(20):
        print(f"  {count:3d}  {entity_type}")

    print(f"\n=== value_type ({len(value_types)}종) ===")
    for value_type, count in value_types.most_common():
        print(f"  {count:3d}  {value_type}")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        choices=[
            LLM_WIKI_DATASET,
            CHANNEL_TALK_RAW_DATASET,
            CHANNEL_TALK_NORMALIZED_DATASET,
        ],
        default=LLM_WIKI_DATASET,
        help="raw와 normalized를 비교하면 레이어 1의 효과가 보인다",
    )
    parser.add_argument("--limit", type=int, default=None, help="처리할 원문 수")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument(
        "--round-size",
        type=int,
        default=5,
        help="한 라운드에서 같은 어휘를 공유할 원문 수",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--capacity",
        choices=[capacity.value for capacity in ModelCapacity],
        default=ModelCapacity.LARGE.value,
    )
    args = parser.parse_args()

    sources = _load_sources(args.dataset)
    if args.limit is not None:
        sources = sources[: args.limit]

    service = get_llm_service(
        provider=LlmProvider.AWS_BEDROCK,
        model_capacity=ModelCapacity(args.capacity),
        streaming=False,
    )
    extractor = StructuredKnowledgeExtractor(service.get_llm())

    print(
        f"데이터셋 {args.dataset}, 원문 {len(sources)}건, "
        f"라운드 {args.round_size}건씩, "
        f"동시 {args.concurrency}건, 모델 {args.capacity}"
    )

    semaphore = asyncio.Semaphore(args.concurrency)
    vocabulary = ExtractionVocabulary()
    results: list[dict] = []

    # 라운드 안은 병렬로 돌리되 어휘는 라운드 경계에서만 넓힌다.
    for round_index in range(0, len(sources), args.round_size):
        batch_sources = sources[round_index : round_index + args.round_size]
        number = round_index // args.round_size + 1
        keys = ", ".join(source.key for source in batch_sources)
        print(f"\nround {number} ({keys})")

        round_results = await asyncio.gather(
            *(
                _extract_one(extractor, source, semaphore, vocabulary)
                for source in batch_sources
            )
        )
        results.extend(round_results)
        vocabulary = _grow_vocabulary(vocabulary, list(round_results), number)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = args.output_dir / f"extraction_{args.dataset}_{stamp}.json"
    out_path.write_text(
        json.dumps(list(results), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    _summarize(list(results))
    _report_source_field_leakage(
        list(results),
        _build_source_field_index(args.dataset),
    )
    print(f"\n결과: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
