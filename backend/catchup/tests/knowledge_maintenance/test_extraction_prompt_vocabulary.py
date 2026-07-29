"""사전이 실린 어휘가 프롬프트와 실행에서 어떻게 다뤄지는지 검증한다.

`test_vocabulary_dictionary.py`가 계약 자체를 본다면 여기서는 그 계약이
프롬프트 렌더와 추출 러너의 라운드 진행에 닿는 지점을 본다.
"""

from __future__ import annotations

from catchup.evaluation.run_extraction_pipeline import _next_vocabulary
from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary
from catchup.knowledge_maintenance.contracts.extraction import PredicateEntry
from catchup.knowledge_maintenance.contracts.extraction import RelationTypeEntry
from catchup.prompts.loader import prompt_loader

TEMPLATE = "knowledge_maintenance/extract_knowledge_candidates.j2"


def _render(vocabulary: ExtractionVocabulary | None) -> str:
    return prompt_loader.get_prompt(
        TEMPLATE,
        vocabulary=vocabulary,
        metadata_entities=(),
        content="본문",
        source_type="channel_talk",
    )


def _entry() -> PredicateEntry:
    return PredicateEntry(
        name="rate_limit_per_minute",
        definition="분당 허용되는 API 호출 횟수",
        domain=("api",),
        value_type="number",
        examples=("분당 60회입니다 → 60",),
    )


def _round_results(*predicates: str) -> list[dict]:
    """`_grow_vocabulary`가 읽는 라운드 결과 모양을 만든다."""
    return [
        {
            "status": "ok",
            "batch": {
                "claims": [
                    {"predicate": predicate} for predicate in predicates
                ],
                "relation_assertions": [],
            },
        }
    ]


def test_entry_definition_renders() -> None:
    rendered = _render(
        ExtractionVocabulary(snapshot_id="2", predicate_entries=(_entry(),))
    )
    assert "분당 허용되는 API 호출 횟수" in rendered
    assert "(number)" in rendered
    assert "subjects: api" in rendered


def test_enum_range_renders() -> None:
    rendered = _render(
        ExtractionVocabulary(
            snapshot_id="2",
            predicate_entries=(
                PredicateEntry(
                    name="plan_tier",
                    definition="구독 등급",
                    value_type="enum",
                    enum_values=("free", "pro"),
                ),
            ),
            relation_type_entries=(
                RelationTypeEntry(
                    name="depends_on",
                    definition="앞의 것이 동작하려면 뒤의 것이 필요하다",
                    domain=("feature",),
                    range_=("system",),
                ),
            ),
        )
    )
    assert "one of: free / pro" in rendered
    assert "subjects: feature" in rendered
    assert "targets: system" in rendered


def test_name_only_vocabulary_still_renders() -> None:
    """v1 스냅샷은 이름 목록으로 그대로 렌더된다."""
    rendered = _render(
        ExtractionVocabulary(snapshot_id="1", predicates=("status",))
    )
    assert "- status" in rendered


def test_no_vocabulary_hides_the_section() -> None:
    assert "Vocabulary already in use" not in _render(None)
    assert "Vocabulary already in use" not in _render(ExtractionVocabulary())


def test_names_without_entry_are_listed_next_to_the_dictionary() -> None:
    """사전에 없는 이름도 함께 실려야 재사용을 유도할 수 있다.

    entry가 있다고 이름 목록을 통째로 감추면 관찰로 늘어난 용어가 다음
    문서의 프롬프트에서 사라진다.
    """
    rendered = _render(
        ExtractionVocabulary(
            snapshot_id="2",
            predicates=("rate_limit_per_minute", "release_month"),
            predicate_entries=(_entry(),),
            relation_types=("depends_on",),
            relation_type_entries=(
                RelationTypeEntry(
                    name="blocks",
                    definition="앞의 것이 끝나야 뒤의 것을 할 수 있다",
                ),
            ),
        )
    )
    assert "분당 허용되는 API 호출 횟수" in rendered
    assert "- release_month" in rendered
    assert "- depends_on" in rendered
    # 정의가 있는 이름을 정의 없는 목록에 또 적으면 안 된다.
    assert rendered.count("rate_limit_per_minute") == 1


def test_pinned_run_keeps_the_vocabulary_identical() -> None:
    """고정 버전 실행은 어휘를 키우지 않는다.

    키우면 같은 snapshot_id에 다른 내용이 담겨 `ontology.ensure`가 두
    번째 라운드에서 충돌로 실행을 통째로 멈춘다.
    """
    base = ExtractionVocabulary(snapshot_id="v1", predicate_entries=(_entry(),))
    after = _next_vocabulary(
        base,
        _round_results("rate_limit_per_minute", "release_month"),
        round_index=2,
        pinned=True,
    )
    assert after == base
    assert after.snapshot_id == "v1"
    assert "release_month" not in after.predicates


def test_unpinned_run_still_grows() -> None:
    """버전을 고정하지 않은 관찰 실행은 예전처럼 어휘를 넓힌다."""
    after = _next_vocabulary(
        ExtractionVocabulary(),
        _round_results("release_month"),
        round_index=1,
        pinned=False,
    )
    assert "release_month" in after.predicates
    assert after.snapshot_id == "round-1"
