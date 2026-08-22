"""preset 카탈로그 상수가 서로 어긋나지 않는지 검사한다."""

from catchup.knowledge_maintenance.domain.actor_identity import ACTOR_EXPOSURES
from catchup.knowledge_maintenance.domain.artifact_definition import (
    validate_selection_spec,
)
from catchup.knowledge_maintenance.domain.preset_catalog import DEFAULT_PURPOSE_SENTENCE
from catchup.knowledge_maintenance.domain.preset_catalog import (
    DEFAULT_STYLE_INSTRUCTION,
)
from catchup.knowledge_maintenance.domain.preset_catalog import PRESET_DOMAINS
from catchup.knowledge_maintenance.domain.preset_catalog import PRESET_STYLES
from catchup.knowledge_maintenance.domain.preset_catalog import find_actor_exposure
from catchup.knowledge_maintenance.domain.preset_catalog import find_kind
from catchup.knowledge_maintenance.domain.preset_catalog import find_kind_by_name
from catchup.knowledge_maintenance.domain.preset_catalog import find_purpose
from catchup.knowledge_maintenance.domain.preset_catalog import find_style
from catchup.knowledge_maintenance.domain.preset_catalog import layout_for_kind


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


def test_kind_names_are_unique_across_domains() -> None:
    """kind 이름이 도메인을 가로질러도 겹치지 않는다.

    `find_kind_by_name`은 도메인을 모른 채 저장된 kind를 되짚는 조회라
    처음 걸린 것을 돌려준다. 이름이 겹치면 어느 도메인의 종류로 풀릴지
    카탈로그에 적힌 차례에 달리고, 목적 문장이 조용히 뒤바뀐다.
    """
    names = [
        preset_kind.kind
        for domain in PRESET_DOMAINS
        for preset_kind in domain.kinds
    ]

    assert len(names) == len(set(names))
    for name in names:
        assert find_kind_by_name(name) is not None


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
    assert len(voc.purposes) == 6
    assert len(voc.kinds) == 5


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
    found = find_purpose("voc.complaint_patterns")
    assert found is not None
    domain, purpose = found
    assert domain.id == "voc"
    assert purpose.recommended_kind == "complaint_topic_brief"
    assert purpose in domain.purposes


def test_find_purpose_returns_none_for_unknown_id() -> None:
    """모르는 목적 id는 조용히 빈 값으로 돌려준다."""
    assert find_purpose("voc.nonexistent") is None


def test_find_kind_looks_inside_the_given_domain_only() -> None:
    """kind 조회는 넘겨준 도메인 안에서만 찾는다."""
    found = find_purpose("voc.top_requests")
    assert found is not None
    voc = found[0]
    preset_kind = find_kind(voc, "faq_answer")
    assert preset_kind is not None
    assert preset_kind.kind == "faq_answer"
    other = next(d for d in PRESET_DOMAINS if d.id == "product")
    assert find_kind(other, "faq_answer") is None


def test_find_style_matches_the_catalog() -> None:
    """문체 조회는 카탈로그에 있는 id에만 응답한다."""
    style = find_style("style.support_guide")
    assert style is not None
    assert style.id == "style.support_guide"
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


def test_voc_domain_exposes_name_and_email() -> None:
    """VOC 도메인은 이름과 이메일을 함께 드러내는 수준으로 고정돼 있다."""
    domain = next(d for d in PRESET_DOMAINS if d.id == "voc")
    assert domain.actor_exposure == "name_email"


def test_actor_exposure_follows_purpose_domain() -> None:
    """노출 수준은 목적이 속한 도메인을 따라가고, 모르면 기본값이다."""
    voc_purpose = next(d for d in PRESET_DOMAINS if d.id == "voc").purposes[0].id
    assert find_actor_exposure(voc_purpose) == "name_email"
    assert find_actor_exposure(None) == "name"
    assert find_actor_exposure("no-such-purpose") == "name"


def test_every_domain_exposure_is_a_known_level() -> None:
    """모든 도메인의 노출 수준이 규약에 있는 값이다."""
    assert all(d.actor_exposure in ACTOR_EXPOSURES for d in PRESET_DOMAINS)


def test_voc_seed_carries_template_predicates() -> None:
    """양식이 채우는 칸이 전부 seed 어휘에 선언돼 있다."""
    voc = next(d for d in PRESET_DOMAINS if d.id == "voc")
    names = {p.name for p in voc.seed_vocabulary.predicate_entries}
    assert {
        "last_reported_at",
        "usage_context",
        "requester_role",
        "frequency",
        "support_status",
        "workaround",
        "complaint_status",
        "expected_behavior",
        "reproduction_steps",
        "impact",
        "guidance",
        "faq_status",
        "faq_category",
        "current_answer",
        "internal_notes",
        "last_confirmed_at",
        "industry",
        "company_size",
        "adopted_at",
        "usage_pattern",
        "account_request_status",
    } <= names
    status = voc.seed_vocabulary.predicate_entry("request_status")
    assert status is not None
    assert status.enum_values == (
        "collected",
        "under_review",
        "confirmed",
        "shipped",
        "on_hold",
    )
    entity_names = {e.name for e in voc.seed_vocabulary.entity_type_entries}
    assert entity_names >= {"faq_question"}
    relation_names = {r.name for r in voc.seed_vocabulary.relation_type_entries}
    assert relation_names >= {"related_question"}


def test_enum_predicates_name_their_korean_labels() -> None:
    """enum 칸은 허용 값과 그 한국어 뜻을 정의문에 함께 적는다."""
    voc = next(d for d in PRESET_DOMAINS if d.id == "voc")
    for name in (
        "request_status",
        "complaint_status",
        "faq_status",
        "faq_category",
        "account_request_status",
        "support_status",
    ):
        entry = voc.seed_vocabulary.predicate_entry(name)
        assert entry is not None
        assert entry.value_type == "enum" and entry.enum_values
        assert any(v in entry.definition for v in entry.enum_values)


def test_voc_kinds_match_the_planning_templates() -> None:
    """VOC 문서 종류가 양식 5종으로만 등재돼 있다."""
    voc = next(d for d in PRESET_DOMAINS if d.id == "voc")
    assert [k.kind for k in voc.kinds] == [
        "feature_request_status",
        "complaint_topic_brief",
        "faq_answer",
        "customer_voice_profile",
        "customer_history",
    ]
    assert find_kind_by_name("request_priority_board") is None
    assert find_kind_by_name("churn_risk_watch") is None


def test_feature_request_kind_selects_template_sections() -> None:
    """기능 요청 문서가 양식이 요구하는 칸을 차례대로 고른다."""
    voc = next(d for d in PRESET_DOMAINS if d.id == "voc")
    preset_kind = find_kind(voc, "feature_request_status")
    assert preset_kind is not None
    spec = preset_kind.spec_template()
    assert spec.predicate_sections == (
        "request_status",
        "request_priority",
        "request_count",
        "first_reported_at",
        "last_reported_at",
        "usage_context",
        "requester_role",
        "frequency",
        "support_status",
        "workaround",
    )


def test_top_requests_purpose_keeps_request_count_in_its_recommended_kind() -> (
    None
):
    """많이 들어온 요구를 보는 목적이 접수 횟수를 근거로 남긴다.

    목적과 문서 종류의 짝을 함께 본다. 종류의 절 목록만 보면, 목적이
    가리키는 종류가 바뀌었을 때 목적이 근거 없는 문서를 받게 되는 것을
    놓친다.
    """
    found = find_purpose("voc.top_requests")
    assert found is not None
    _, purpose = found
    preset_kind = find_kind_by_name(purpose.recommended_kind)
    assert preset_kind is not None
    sections = preset_kind.spec_template().predicate_sections
    assert sections is not None
    assert "request_count" in sections


def test_styles_are_the_three_presets_plus_custom() -> None:
    """문체는 preset 3종과 직접 지정 하나로 고정된다."""
    assert [s.id for s in PRESET_STYLES] == [
        "style.wiki_standard",
        "style.support_guide",
        "style.report_summary",
        "style.custom",
    ]
    assert find_style("style.faq") is None
    assert DEFAULT_STYLE_INSTRUCTION == PRESET_STYLES[0].instruction


def test_voc_purposes_map_to_surviving_kinds() -> None:
    """목적 6종이 전부 살아 있는 문서 종류를 가리킨다."""
    voc = next(d for d in PRESET_DOMAINS if d.id == "voc")
    mapping = {p.id: p.recommended_kind for p in voc.purposes}
    assert mapping == {
        "voc.request_status_tracking": "feature_request_status",
        "voc.top_requests": "feature_request_status",
        "voc.complaint_patterns": "complaint_topic_brief",
        "voc.customer_understanding": "customer_history",
        "voc.faq_consistency": "faq_answer",
        "voc.account_requests": "customer_voice_profile",
    }
    assert find_purpose("voc.churn_signals") is None


def test_every_kind_layout_keys_exist_in_its_selection_spec() -> None:
    """레이아웃이 부르는 칸이 전부 그 종류의 선택 규칙 안에 있다."""
    for domain in PRESET_DOMAINS:
        for preset_kind in domain.kinds:
            layout = preset_kind.layout
            assert layout is not None, preset_kind.kind
            spec = preset_kind.spec_template()
            allowed = set(spec.predicate_sections or ()) | {
                " \u2192 ".join(
                    f"{s.relation_type}({s.direction})" for s in path.steps
                )
                for path in spec.relation_paths
            }
            keys = {key for key, _ in layout.sections}
            for group in layout.table_groups:
                keys |= set(group.section_keys)
            keys |= set(layout.always_show)
            assert keys <= allowed, (preset_kind.kind, keys - allowed)


def test_layout_for_kind_returns_none_for_unknown() -> None:
    """모르는 종류를 물으면 레이아웃이 없다고 답한다."""
    assert layout_for_kind("no_such_kind") is None
    assert layout_for_kind("feature_request_status") is not None


def test_every_table_group_key_is_listed_in_sections() -> None:
    """표로 합칠 칸이 전부 sections 순서에도 올라 있는지 본다."""
    for domain in PRESET_DOMAINS:
        for preset_kind in domain.kinds:
            layout = preset_kind.layout
            assert layout is not None, preset_kind.kind
            section_keys = {key for key, _ in layout.sections}
            for group in layout.table_groups:
                missing = set(group.section_keys) - section_keys
                assert not missing, (preset_kind.kind, group.key, missing)
