"""부트스트랩 workspace의 predicate에 value_type 초안을 붙인다.

어휘를 처음 세울 때 predicate 이름은 관찰에서 저절로 자라지만 그 값이
숫자인지 날짜인지 몇 갈래 중 하나인지는 아무도 적어주지 않는다. 모순
판정은 그 치역(value_type)이 있어야 값을 비교할 수 있으므로 누군가는
채워야 한다. 이 러너가 그 초안을 만든다 — 자란 predicate마다 실제로
관찰된 값 몇 개를 모델에게 보여주고 치역을 제안받는다.

초안까지만이다. 발행은 사람이 한다. 초안 JSON을 사람이 읽고 고친 뒤
`publish_vocabulary_snapshot --input <path>`로 올린다. 그래서 이
모듈은 DB에 아무것도 쓰지 않고, 저장 직전에 발행이 읽을 계약인
`ExtractionVocabulary.model_validate`를 스스로 통과시켜 본다.

모델이 지어낸 predicate와 계약에 없는 치역은 조용히 통과시키지 않고
거부한다. 초안이라도 사람이 검토할 대상은 실제로 관찰된 것뿐이어야
한다.

실행:
    uv run python -m catchup.evaluation.longmemeval.draft_vocabulary \\
        --workspace-id 901 \\
        --output experiments/longmemeval/vocabulary_draft.json \\
        --usage-out experiments/longmemeval/vocabulary_draft_usage.json
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from collections.abc import Iterable
from collections.abc import Mapping
from collections.abc import Sequence
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Any
from typing import Literal

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from catchup.components.llm.constants import LlmProvider
from catchup.components.llm.constants import ModelCapacity
from catchup.components.llm.factory import get_llm_service
from catchup.configs.config import settings
from catchup.db.models import KnowledgeClaimCandidate
from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary
from catchup.knowledge_maintenance.contracts.extraction import PredicateEntry

DEFAULT_WORKSPACE_ID = 901
DEFAULT_SNAPSHOT_ID = "draft"
# 한 번에 너무 많은 predicate를 물으면 뒤쪽 정의가 뭉개진다. 배치로
# 나눠 묻고 사용량은 합산한다.
DEFAULT_BATCH_SIZE = 20
DEFAULT_SAMPLE_LIMIT = 5
# 값 하나가 길면 프롬프트가 값 하나로 채워진다. 치역 판단에는 앞부분만
# 있으면 충분하다.
VALUE_PREVIEW_LIMIT = 120

VALUE_TYPES = ("number", "date", "boolean", "enum", "text")

PROMPT_HEADER = """\
You are drafting a closed vocabulary for a knowledge extraction pipeline.

For each predicate below you are given the value types that were observed
in raw extraction candidates and up to a few real observed values. Decide
the value_type each predicate should be constrained to.

Rules:
- value_type must be exactly one of: number, date, boolean, enum, text.
- Choose "enum" only when the observed values clearly fall into a small,
  closed set of categories. Then list every allowed value in enum_values
  as lowercase snake_case English identifiers, and make sure every
  observed value maps onto one of them.
- Choose "date" for calendar dates, "number" for quantities, "boolean"
  for yes/no facts, and "text" for open-ended values such as names,
  places, or free descriptions.
- Write the definition in Korean, one or two sentences, saying what the
  predicate asserts about its subject.
- domain lists the entity types this predicate applies to, in English
  snake_case. Leave it empty when you cannot tell.
- Emit exactly one entry per predicate given, using the predicate name
  verbatim. Do not invent predicates.

Predicates:
"""


class VocabularyDraftError(ValueError):
    """초안이 발행 계약을 만족하지 못했음을 알린다."""


@dataclass(frozen=True)
class PredicateSample:
    """predicate 하나와 그 아래에서 관찰된 값 샘플을 담는다."""

    predicate: str
    observed_value_types: tuple[str, ...] = ()
    values: tuple[str, ...] = ()
    occurrences: int = 0


@dataclass(frozen=True)
class UsageTotals:
    """LLM 호출이 쓴 토큰을 합산한다."""

    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        """입력과 출력 토큰을 합친 수를 나타낸다."""
        return self.input_tokens + self.output_tokens

    def plus(self, other: UsageTotals) -> UsageTotals:
        """다른 집계를 더한 새 집계를 만든다."""
        return UsageTotals(
            calls=self.calls + other.calls,
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
        )

    def as_dict(self) -> dict[str, int]:
        """비용 계측 파일에 담을 형태로 바꾼다."""
        return {
            "calls": self.calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass(frozen=True)
class DraftResponse:
    """한 번의 초안 호출이 돌려준 항목과 사용량을 담는다.

    항목을 `PredicateEntry`가 아니라 raw mapping으로 받는다. 모델이 계약
    밖의 값을 냈는지 판정하는 자리는 이 모듈이어야 하기 때문이다.
    """

    entries: tuple[Mapping[str, Any], ...] = ()
    usage: UsageTotals = field(default_factory=UsageTotals)


@dataclass(frozen=True)
class DraftOutcome:
    """검증을 마친 초안 어휘와 총 사용량을 담는다."""

    vocabulary: ExtractionVocabulary
    usage: UsageTotals


DraftFn = Callable[[Sequence[PredicateSample]], DraftResponse]


class PredicateDraft(BaseModel):
    """모델에게 요구할 predicate 초안 한 건의 형태를 정의한다."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="The predicate name, copied verbatim.")
    definition: str = Field(description="Korean, one or two sentences.")
    domain: list[str] = Field(default_factory=list)
    value_type: Literal["number", "date", "boolean", "enum", "text"]
    enum_values: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)


class PredicateDraftBatch(BaseModel):
    """한 번의 호출로 받을 초안 묶음을 정의한다."""

    model_config = ConfigDict(extra="forbid")

    entries: list[PredicateDraft] = Field(default_factory=list)


def _preview(value: Any) -> str:
    """JSONB 값 하나를 프롬프트에 실을 짧은 문자열로 만든다."""
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=False)
    text = " ".join(text.split())
    if len(text) > VALUE_PREVIEW_LIMIT:
        return text[:VALUE_PREVIEW_LIMIT] + "…"
    return text


def build_prompt(samples: Sequence[PredicateSample]) -> str:
    """predicate와 관찰 값을 모델이 읽을 형태로 늘어놓는다."""
    lines = [PROMPT_HEADER]
    for sample in samples:
        observed = ", ".join(sample.observed_value_types) or "unknown"
        lines.append(
            f"- {sample.predicate} "
            f"(observed value_type: {observed}, "
            f"occurrences: {sample.occurrences})"
        )
        for value in sample.values:
            lines.append(f"    · {value}")
    return "\n".join(lines)


def usage_from_message(message: Any) -> UsageTotals:
    """응답 메시지의 usage_metadata를 사용량 집계로 옮긴다.

    구조화 출력을 쓰면 파싱된 모델에는 토큰 수가 남지 않는다. 그래서
    `include_raw=True`로 받은 원본 메시지에서 읽는다. 메타데이터가 아예
    없더라도 호출은 있었으므로 호출 수는 센다.
    """
    metadata = getattr(message, "usage_metadata", None) or {}
    return UsageTotals(
        calls=1,
        input_tokens=int(metadata.get("input_tokens") or 0),
        output_tokens=int(metadata.get("output_tokens") or 0),
    )


def _batched(
    samples: Sequence[PredicateSample],
    size: int,
) -> Iterable[Sequence[PredicateSample]]:
    """샘플을 배치 크기만큼 잘라 내보낸다."""
    for start in range(0, len(samples), size):
        yield samples[start : start + size]


def _to_entry(
    payload: Mapping[str, Any],
    *,
    requested: frozenset[str],
) -> PredicateEntry:
    """초안 한 건을 발행 계약의 사전 항목으로 확정한다."""
    name = str(payload.get("name", "")).strip()
    if name not in requested:
        raise VocabularyDraftError(
            f"요청하지 않은 predicate를 초안이 담았다: {name!r}"
        )
    try:
        return PredicateEntry.model_validate(
            {
                "name": name,
                "definition": payload.get("definition", ""),
                "domain": tuple(payload.get("domain") or ()),
                "value_type": payload.get("value_type"),
                "enum_values": tuple(payload.get("enum_values") or ()),
                "examples": tuple(payload.get("examples") or ()),
            }
        )
    except ValidationError as error:
        raise VocabularyDraftError(
            f"predicate {name!r}의 초안이 계약을 어겼다 "
            f"(허용 value_type: {', '.join(VALUE_TYPES)}): {error}"
        ) from error


def draft_vocabulary(
    samples: Sequence[PredicateSample],
    draft: DraftFn,
    *,
    snapshot_id: str = DEFAULT_SNAPSHOT_ID,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> DraftOutcome:
    """관찰 샘플로 어휘 초안을 만들고 발행 계약을 통과시킨다."""
    samples = list(samples)
    if not samples:
        raise VocabularyDraftError(
            "value_type을 붙일 predicate가 하나도 없다."
        )

    requested = frozenset(sample.predicate for sample in samples)
    entries: list[PredicateEntry] = []
    seen: set[str] = set()
    usage = UsageTotals()

    for batch in _batched(samples, max(batch_size, 1)):
        response = draft(batch)
        usage = usage.plus(response.usage)
        for payload in response.entries:
            entry = _to_entry(payload, requested=requested)
            if entry.name in seen:
                raise VocabularyDraftError(
                    f"predicate {entry.name!r}가 초안에 두 번 나왔다."
                )
            seen.add(entry.name)
            entries.append(entry)

    ordered = {entry.name: entry for entry in entries}
    entries = [
        ordered[sample.predicate]
        for sample in samples
        if sample.predicate in ordered
    ]

    # 저장 직전에 발행이 읽는 그 경로로 한 번 더 통과시킨다. 초안 파일이
    # publish 단계에서 처음 거부되면 LLM 호출 비용이 통째로 버려진다.
    vocabulary = ExtractionVocabulary.model_validate(
        {
            "snapshot_id": snapshot_id,
            "predicate_entries": [entry.model_dump() for entry in entries],
        }
    )
    return DraftOutcome(vocabulary=vocabulary, usage=usage)


def load_predicate_samples(
    session: Session,
    *,
    workspace_id: int,
    sample_limit: int = DEFAULT_SAMPLE_LIMIT,
) -> tuple[PredicateSample, ...]:
    """부트스트랩 workspace의 predicate와 값 샘플을 읽는다.

    읽기 전용이다. candidate 테이블을 직접 본다 — 아직 승인 경계를 지나지
    않은 관찰이 어휘의 재료이기 때문이다.
    """
    ranked = (
        select(
            KnowledgeClaimCandidate.predicate.label("predicate"),
            KnowledgeClaimCandidate.value_type.label("value_type"),
            KnowledgeClaimCandidate.value.label("value"),
            func.row_number()
            .over(
                partition_by=KnowledgeClaimCandidate.predicate,
                order_by=KnowledgeClaimCandidate.created_at.desc(),
            )
            .label("rank"),
            func.count()
            .over(partition_by=KnowledgeClaimCandidate.predicate)
            .label("occurrences"),
        )
        .where(KnowledgeClaimCandidate.workspace_id == workspace_id)
        .subquery()
    )

    rows = session.execute(
        select(
            ranked.c.predicate,
            ranked.c.value_type,
            ranked.c.value,
            ranked.c.occurrences,
        )
        .where(ranked.c.rank <= max(sample_limit, 1))
        .order_by(ranked.c.predicate, ranked.c.rank)
    ).all()

    grouped: dict[str, dict[str, Any]] = {}
    for predicate, value_type, value, occurrences in rows:
        bucket = grouped.setdefault(
            predicate,
            {"types": [], "values": [], "occurrences": occurrences},
        )
        if value_type not in bucket["types"]:
            bucket["types"].append(value_type)
        bucket["values"].append(_preview(value))

    return tuple(
        PredicateSample(
            predicate=predicate,
            observed_value_types=tuple(bucket["types"]),
            values=tuple(bucket["values"]),
            occurrences=int(bucket["occurrences"]),
        )
        for predicate, bucket in sorted(grouped.items())
    )


def bedrock_draft_fn(llm: BaseChatModel) -> DraftFn:
    """Bedrock 모델을 초안 함수로 감싼다.

    `include_raw=True`로 받는다. 파싱된 결과만 받으면 토큰 사용량을 셀
    수 없는데, 초안 비용 계측이 이 러너의 요건이기 때문이다.
    """
    structured = llm.with_structured_output(
        PredicateDraftBatch,
        method="function_calling",
        include_raw=True,
    )

    def draft(samples: Sequence[PredicateSample]) -> DraftResponse:
        result = structured.invoke(build_prompt(samples))
        parsed = result.get("parsed")
        usage = usage_from_message(result.get("raw"))
        if parsed is None:
            raise VocabularyDraftError(
                f"초안 출력이 구조화 계약을 만족하지 않았다: "
                f"{result.get('parsing_error')}"
            )
        return DraftResponse(
            entries=tuple(item.model_dump() for item in parsed.entries),
            usage=usage,
        )

    return draft


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace-id",
        type=int,
        default=DEFAULT_WORKSPACE_ID,
        help="관찰 candidate를 읽어올 부트스트랩 workspace를 정한다.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="초안 어휘 JSON을 저장할 경로를 정한다.",
    )
    parser.add_argument(
        "--usage-out",
        type=Path,
        default=None,
        help="토큰 사용량 집계를 저장할 경로를 정한다.",
    )
    parser.add_argument("--snapshot-id", default=DEFAULT_SNAPSHOT_ID)
    parser.add_argument(
        "--sample-limit",
        type=int,
        default=DEFAULT_SAMPLE_LIMIT,
    )
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument(
        "--capacity",
        choices=[capacity.value for capacity in ModelCapacity],
        default=ModelCapacity.LARGE.value,
    )
    args = parser.parse_args()

    engine = create_engine(settings.sqlalchemy_database_url)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        with session_factory() as session:
            samples = load_predicate_samples(
                session,
                workspace_id=args.workspace_id,
                sample_limit=args.sample_limit,
            )
        if not samples:
            print(
                f"workspace {args.workspace_id}에 claim candidate가 없다. "
                f"추출을 먼저 돌린다."
            )
            return 1

        service = get_llm_service(
            provider=LlmProvider.AWS_BEDROCK,
            model_capacity=ModelCapacity(args.capacity),
            streaming=False,
        )
        outcome = draft_vocabulary(
            samples,
            bedrock_draft_fn(service.get_llm()),
            snapshot_id=args.snapshot_id,
            batch_size=args.batch_size,
        )
    finally:
        engine.dispose()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            outcome.vocabulary.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    if args.usage_out is not None:
        args.usage_out.parent.mkdir(parents=True, exist_ok=True)
        args.usage_out.write_text(
            json.dumps(
                {
                    "workspace_id": args.workspace_id,
                    "capacity": args.capacity,
                    "predicates": len(outcome.vocabulary.predicate_entries),
                    **outcome.usage.as_dict(),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    print(
        f"초안 {len(outcome.vocabulary.predicate_entries)}종 → "
        f"{args.output} (호출 {outcome.usage.calls}회, "
        f"토큰 {outcome.usage.total_tokens})"
    )
    print(
        "발행은 사람이 한다: uv run python -m "
        "catchup.evaluation.publish_vocabulary_snapshot "
        f"--workspace-id <id> --input {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
