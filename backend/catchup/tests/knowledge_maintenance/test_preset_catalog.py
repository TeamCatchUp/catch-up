"""preset 카탈로그 상수가 서로 어긋나지 않는지 검사한다."""

from catchup.knowledge_maintenance.domain.artifact_definition import (
    validate_selection_spec,
)
from catchup.knowledge_maintenance.domain.preset_catalog import DEFAULT_PURPOSE_SENTENCE
from catchup.knowledge_maintenance.domain.preset_catalog import (
    DEFAULT_STYLE_INSTRUCTION,
)
from catchup.knowledge_maintenance.domain.preset_catalog import PRESET_DOMAINS
from catchup.knowledge_maintenance.domain.preset_catalog import PRESET_STYLES
from catchup.knowledge_maintenance.domain.preset_catalog import find_kind
from catchup.knowledge_maintenance.domain.preset_catalog import find_kind_by_name
from catchup.knowledge_maintenance.domain.preset_catalog import find_purpose
from catchup.knowledge_maintenance.domain.preset_catalog import find_style


def test_every_template_name_is_in_its_domain_seed() -> None:
    """템플릿이 참조하는 이름이 전부 그 도메인 seed 안에 있는지 본다."""
    for domain in PRESET_DOMAINS:
        seed = domain.seed_vocabulary
        entity_names = {e.name for e in seed.entity_type_entries}
        relation_names = {r.name for r in seed.relation_type_entries}
        predicate_names = {p.name for p in seed.predicate_entries}
        for preset_kind in domain.kinds:
            spec = preset_kind.spec_template()
            assert set(spec.entity_types) <= entity_names
            for path in spec.relation_paths:
                for step in path.steps:
                    assert step.relation_type in relation_names
            if spec.predicate_sections is not None:
                assert set(spec.predicate_sections) <= predicate_names


def test_template_specs_validate_against_their_seed() -> None:
    """seed 어휘를 기준으로 템플릿이 fail-closed 검증을 통과한다."""
    for domain in PRESET_DOMAINS:
        for preset_kind in domain.kinds:
            validate_selection_spec(
                preset_kind.spec_template(), domain.seed_vocabulary
            )


def test_purpose_ids_are_namespaced_by_domain() -> None:
    """목적 id가 전부 도메인 슬러그 접두를 지킨다."""
    for domain in PRESET_DOMAINS:
        for purpose in domain.purposes:
            assert purpose.id.startswith(f"{domain.id}.")


def test_recommended_kind_exists_in_the_same_domain() -> None:
    """추천 kind가 같은 도메인의 kind 목록 안에 있다."""
    for domain in PRESET_DOMAINS:
        kinds = {preset_kind.kind for preset_kind in domain.kinds}
        for purpose in domain.purposes:
            assert purpose.recommended_kind in kinds


def test_templates_are_deterministic() -> None:
    """같은 템플릿을 두 번 불러도 같은 값이 나온다."""
    for domain in PRESET_DOMAINS:
        for preset_kind in domain.kinds:
            assert preset_kind.spec_template() == preset_kind.spec_template()


def test_ids_fit_the_stored_column_widths() -> None:
    """목적·문체 id는 64자, kind는 32자 안에 들어간다."""
    for domain in PRESET_DOMAINS:
        for purpose in domain.purposes:
            assert len(purpose.id) <= 64
        for preset_kind in domain.kinds:
            assert len(preset_kind.kind) <= 32
    for style in PRESET_STYLES:
        assert len(style.id) <= 64


def test_voc_domain_is_fully_populated() -> None:
    """VOC 도메인만 콘텐츠가 채워져 있다."""
    found = find_purpose("voc.top_requests")
    assert found is not None
    voc = found[0]
    assert len(voc.purposes) == 5
    assert len(voc.kinds) == 6


def test_empty_domains_are_listed_with_no_choices() -> None:
    """나머지 도메인은 구조만 등재된다."""
    empty = [d for d in PRESET_DOMAINS if d.id != "voc"]
    assert len(empty) == 5
    assert all(not d.purposes and not d.kinds for d in empty)


def test_domain_and_purpose_and_kind_ids_are_unique() -> None:
    """id가 겹치면 조회가 갈리므로 전역 유일성을 본다."""
    domain_ids = [d.id for d in PRESET_DOMAINS]
    assert len(domain_ids) == len(set(domain_ids))
    purpose_ids = [p.id for d in PRESET_DOMAINS for p in d.purposes]
    assert len(purpose_ids) == len(set(purpose_ids))
    kind_ids = [k.kind for d in PRESET_DOMAINS for k in d.kinds]
    assert len(kind_ids) == len(set(kind_ids))
    style_ids = [s.id for s in PRESET_STYLES]
    assert len(style_ids) == len(set(style_ids))


def test_find_purpose_returns_its_owning_domain() -> None:
    """목적을 찾으면 그 목적이 속한 도메인이 함께 나온다."""
    found = find_purpose("voc.churn_signals")
    assert found is not None
    domain, purpose = found
    assert domain.id == "voc"
    assert purpose.recommended_kind == "churn_risk_watch"
    assert purpose in domain.purposes


def test_find_purpose_returns_none_for_unknown_id() -> None:
    """모르는 목적 id는 조용히 빈 값으로 돌려준다."""
    assert find_purpose("voc.nonexistent") is None


def test_find_kind_looks_inside_the_given_domain_only() -> None:
    """kind 조회는 넘겨준 도메인 안에서만 찾는다."""
    found = find_purpose("voc.top_requests")
    assert found is not None
    voc = found[0]
    preset_kind = find_kind(voc, "request_priority_board")
    assert preset_kind is not None
    assert preset_kind.kind == "request_priority_board"
    other = next(d for d in PRESET_DOMAINS if d.id == "product")
    assert find_kind(other, "request_priority_board") is None


def test_find_style_matches_the_catalog() -> None:
    """문체 조회는 카탈로그에 있는 id에만 응답한다."""
    style = find_style("style.faq")
    assert style is not None
    assert style.id == "style.faq"
    assert find_style("style.unknown") is None


def test_every_purpose_recommends_a_kind_resolvable_by_find_kind() -> None:
    """추천 kind가 조회 함수로도 실제로 풀린다."""
    for domain in PRESET_DOMAINS:
        for purpose in domain.purposes:
            assert find_kind(domain, purpose.recommended_kind) is not None


def test_seed_vocabulary_has_no_version_pinned_yet() -> None:
    """seed 어휘는 발행 시점에 버전이 붙으므로 비어 있다."""
    for domain in PRESET_DOMAINS:
        assert domain.seed_vocabulary.snapshot_id == ""


def test_every_style_carries_an_instruction() -> None:
    """등재된 문체는 전부 비어 있지 않은 지시문을 갖는다."""
    for style in PRESET_STYLES:
        assert style.instruction.strip()


def test_style_instructions_are_distinct() -> None:
    """문체마다 지시문이 달라야 고른 값이 결과를 바꾼다."""
    instructions = [style.instruction for style in PRESET_STYLES]
    assert len(instructions) == len(set(instructions))


def test_default_constants_are_not_empty() -> None:
    """문체·목적을 모를 때 쓸 기본 문장이 준비돼 있다."""
    assert DEFAULT_STYLE_INSTRUCTION.strip()
    assert DEFAULT_PURPOSE_SENTENCE.strip()


def test_find_kind_by_name_reaches_every_registered_kind() -> None:
    """도메인을 몰라도 등재된 kind를 전부 찾는다."""
    for domain in PRESET_DOMAINS:
        for preset_kind in domain.kinds:
            assert find_kind_by_name(preset_kind.kind) is preset_kind


def test_find_kind_by_name_returns_none_for_unknown() -> None:
    """카탈로그 밖 kind는 없음으로 답한다."""
    assert find_kind_by_name("entity_summary") is None
