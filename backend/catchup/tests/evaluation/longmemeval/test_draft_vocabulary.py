"""어휘 value_type 초안 헬퍼가 발행 계약을 지키는지 검증한다.

초안은 사람이 검토한 뒤 `publish_vocabulary_snapshot`이 그대로 읽는
JSON이다. 그래서 이 테스트가 지키는 선은 두 개다 — 저장되는 JSON이
`ExtractionVocabulary.model_validate`를 통과한다는 것, 그리고 모델이
계약에 없는 value_type이나 요청하지 않은 predicate를 지어내면 조용히
통과하지 않고 거부된다는 것이다.

LLM은 실제로 부르지 않는다. 고정 응답을 돌려주는 fake만 쓴다.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from catchup.evaluation.longmemeval.draft_vocabulary import DraftResponse
from catchup.evaluation.longmemeval.draft_vocabulary import PredicateSample
from catchup.evaluation.longmemeval.draft_vocabulary import UsageTotals
from catchup.evaluation.longmemeval.draft_vocabulary import VocabularyDraftError
from catchup.evaluation.longmemeval.draft_vocabulary import build_prompt
from catchup.evaluation.longmemeval.draft_vocabulary import draft_vocabulary
from catchup.evaluation.longmemeval.draft_vocabulary import usage_from_message
from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary


def _sample(name: str = "birth_city") -> PredicateSample:
    """predicate 하나의 관찰 샘플을 만든다."""
    return PredicateSample(
        predicate=name,
        observed_value_types=("text",),
        values=("서울", "부산"),
    )


def _entry(
    name: str = "birth_city",
    value_type: str = "text",
    enum_values: tuple[str, ...] = (),
) -> dict:
    """LLM이 돌려줬다고 가정할 초안 항목 하나를 만든다."""
    return {
        "name": name,
        "definition": f"{name}의 값을 나타낸다.",
        "domain": ["person"],
        "value_type": value_type,
        "enum_values": list(enum_values),
        "examples": ["서울"],
    }


def _fake_draft(*responses: DraftResponse):
    """호출 순서대로 고정 응답을 돌려주는 fake LLM 초안 함수를 만든다."""
    remaining = list(responses)
    calls: list[tuple[PredicateSample, ...]] = []

    def draft(samples):
        calls.append(tuple(samples))
        if not remaining:
            raise AssertionError("예상보다 많이 호출됐다.")
        return remaining.pop(0)

    draft.calls = calls
    return draft


def test_draft_passes_publish_schema():
    """초안 JSON이 발행이 읽는 계약을 그대로 통과한다."""
    draft = _fake_draft(
        DraftResponse(
            entries=(_entry(),),
            usage=UsageTotals(calls=1, input_tokens=10, output_tokens=4),
        )
    )

    outcome = draft_vocabulary(
        [_sample()],
        draft,
        snapshot_id="draft-1",
    )

    payload = json.loads(outcome.vocabulary.model_dump_json())
    reloaded = ExtractionVocabulary.model_validate(payload)
    assert reloaded.snapshot_id == "draft-1"
    assert reloaded.predicates == ("birth_city",)
    entry = reloaded.predicate_entry("birth_city")
    assert entry is not None
    assert entry.value_type == "text"


def test_unknown_value_type_is_rejected():
    """계약에 없는 value_type은 초안 단계에서 거부한다."""
    draft = _fake_draft(
        DraftResponse(entries=(_entry(value_type="uuid"),))
    )

    with pytest.raises(VocabularyDraftError) as error:
        draft_vocabulary([_sample()], draft)

    assert "birth_city" in str(error.value)


def test_enum_without_values_is_rejected():
    """enum이라고 해놓고 허용 값을 비우면 거부한다."""
    draft = _fake_draft(
        DraftResponse(entries=(_entry(value_type="enum"),))
    )

    with pytest.raises(VocabularyDraftError):
        draft_vocabulary([_sample()], draft)


def test_unrequested_predicate_is_rejected():
    """묻지 않은 predicate를 지어내면 거부한다."""
    draft = _fake_draft(
        DraftResponse(entries=(_entry(name="favorite_color"),))
    )

    with pytest.raises(VocabularyDraftError) as error:
        draft_vocabulary([_sample()], draft)

    assert "favorite_color" in str(error.value)


def test_duplicated_predicate_is_rejected():
    """같은 predicate를 두 번 정의하면 거부한다."""
    draft = _fake_draft(
        DraftResponse(entries=(_entry(), _entry()))
    )

    with pytest.raises(VocabularyDraftError):
        draft_vocabulary([_sample()], draft)


def test_usage_totals_are_summed_across_batches():
    """배치를 나눠 불러도 토큰 사용량을 합쳐서 보고한다."""
    draft = _fake_draft(
        DraftResponse(
            entries=(_entry(name="a"),),
            usage=UsageTotals(calls=1, input_tokens=10, output_tokens=3),
        ),
        DraftResponse(
            entries=(_entry(name="b"),),
            usage=UsageTotals(calls=1, input_tokens=7, output_tokens=5),
        ),
    )

    outcome = draft_vocabulary(
        [_sample("a"), _sample("b")],
        draft,
        batch_size=1,
    )

    assert [len(call) for call in draft.calls] == [1, 1]
    assert outcome.usage.calls == 2
    assert outcome.usage.input_tokens == 17
    assert outcome.usage.output_tokens == 8
    assert outcome.usage.as_dict()["total_tokens"] == 25
    assert outcome.vocabulary.predicates == ("a", "b")


def test_empty_samples_are_rejected():
    """샘플이 없으면 부를 것도 없으므로 먼저 멈춘다."""
    draft = _fake_draft()

    with pytest.raises(VocabularyDraftError):
        draft_vocabulary([], draft)


def test_prompt_shows_predicate_and_values():
    """프롬프트에 predicate 이름과 관찰 값이 함께 들어간다."""
    rendered = build_prompt([_sample()])

    assert "birth_city" in rendered
    assert "서울" in rendered
    assert "enum" in rendered


def test_usage_from_message_reads_metadata():
    """응답 메시지의 usage_metadata를 집계 단위로 옮긴다."""
    message = SimpleNamespace(
        usage_metadata={"input_tokens": 11, "output_tokens": 2}
    )

    usage = usage_from_message(message)

    assert usage == UsageTotals(calls=1, input_tokens=11, output_tokens=2)


def test_usage_from_message_without_metadata():
    """usage_metadata가 없어도 호출 수는 세고 토큰은 0으로 둔다."""
    usage = usage_from_message(SimpleNamespace(usage_metadata=None))

    assert usage == UsageTotals(calls=1, input_tokens=0, output_tokens=0)
