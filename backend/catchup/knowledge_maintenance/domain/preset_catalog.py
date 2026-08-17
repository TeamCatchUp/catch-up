"""온보딩이 고르게 할 preset 카탈로그를 담는다.

채널을 만들 때 사용자는 도메인·목적·문체를 고르고, 그 선택이 어떤
어휘와 어떤 선택 규칙으로 풀릴지는 이 카탈로그가 정한다. 값은 전부
상수이고 조회는 순수 함수다 — 같은 선택이면 언제나 같은 결과가
나와야 하기 때문이다.

지금은 VOC(고객 소리) 도메인만 콘텐츠가 채워져 있고, 나머지 도메인은
구조만 등재해 둔다. 목록에 없는 도메인을 나중에 끼워 넣는 것보다,
빈 채로 자리를 잡아 두는 편이 화면과 저장 값의 모양을 미리 고정한다.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from catchup.knowledge_maintenance.contracts.extraction import EntityTypeEntry
from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary
from catchup.knowledge_maintenance.contracts.extraction import PredicateEntry
from catchup.knowledge_maintenance.contracts.extraction import RelationTypeEntry
from catchup.knowledge_maintenance.domain.actor_identity import ACTOR_EXPOSURES
from catchup.knowledge_maintenance.domain.actor_identity import EXPOSURE_NAME
from catchup.knowledge_maintenance.domain.actor_identity import EXPOSURE_NAME_EMAIL
from catchup.knowledge_maintenance.domain.artifact_definition import DIRECTION_IN
from catchup.knowledge_maintenance.domain.artifact_definition import DIRECTION_OUT
from catchup.knowledge_maintenance.domain.artifact_definition import RelationPath
from catchup.knowledge_maintenance.domain.artifact_definition import RelationStep
from catchup.knowledge_maintenance.domain.artifact_definition import SelectionSpec


@dataclass(frozen=True, slots=True)
class PresetKind:
    """문서 종류 하나의 preset을 표현한다.

    Attributes:
        kind: 아티팩트 정의의 kind 값으로 그대로 실린다. 32자 안이다.
        label: 사용자에게 보여줄 짧은 이름을 나타낸다.
        description: 이 종류가 어떤 문서인지 한 줄로 설명한다.
        example_text: 어떤 문서가 나오는지 보여줄 예시를 담는다.
        spec_template: 인자 없이 선택 규칙을 만들어 주는 함수다.
    """

    kind: str
    label: str
    description: str
    example_text: str
    spec_template: Callable[[], SelectionSpec]


@dataclass(frozen=True, slots=True)
class PresetPurpose:
    """채널을 왜 만드는지에 해당하는 목적 preset을 표현한다.

    Attributes:
        id: 채널의 purpose_preset 값으로 그대로 실린다. 64자 안이다.
        label: 사용자에게 보여줄 짧은 이름을 나타낸다.
        recommended_kind: 이 목적에 기본으로 붙일 문서 종류를 가리킨다.
    """

    id: str
    label: str
    recommended_kind: str


@dataclass(frozen=True, slots=True)
class PresetStyle:
    """문서를 어떤 문체로 쓸지 고르는 preset을 표현한다.

    Attributes:
        id: 채널의 style_preset 값으로 그대로 실린다. 64자 안이다.
        label: 사용자에게 보여줄 짧은 이름을 나타낸다.
        instruction: 산문을 쓰는 쪽에 그대로 넘길 지시 한 문단이다.
            라벨과 따로 두는 이유는 라벨이 화면 문구라 언제든 바뀌지만
            지시문은 산출물의 모양을 정하는 계약이기 때문이다.
    """

    id: str
    label: str
    instruction: str


@dataclass(frozen=True, slots=True)
class PresetDomain:
    """한 업무 영역의 preset 묶음을 표현한다.

    Attributes:
        id: 도메인 슬러그를 나타낸다. 목적 id의 접두로도 쓰인다.
        label: 사용자에게 보여줄 짧은 이름을 나타낸다.
        purposes: 이 도메인에서 고를 수 있는 목적들을 담는다.
        kinds: 이 도메인에서 만들 수 있는 문서 종류들을 담는다.
        seed_vocabulary: 이 도메인의 출발 어휘를 담는다. 버전은 발행
            시점에 붙으므로 snapshot_id는 비어 있다.
        actor_exposure: 이 도메인의 문서가 행위자를 어느 수준까지
            드러낼지 정한다. VOC는 사내 도구에서 고객 이메일을
            민감정보로 보지 않는다는 결정으로 name_email이 기본이며,
            전화번호는 어느 단계에도 없다. 채널 override는 열지 않는다.
    """

    id: str
    label: str
    purposes: tuple[PresetPurpose, ...]
    kinds: tuple[PresetKind, ...]
    seed_vocabulary: ExtractionVocabulary
    actor_exposure: str = EXPOSURE_NAME

    def __post_init__(self) -> None:
        """규약 밖 노출 수준을 등재 시점에 막는다."""
        if self.actor_exposure not in ACTOR_EXPOSURES:
            raise ValueError(
                f"알 수 없는 행위자 노출 수준이다: {self.actor_exposure!r}"
            )


# seed는 양식이 predicate 블록으로 채우는 칸을 미리 선언한다. 문서 양식이
# 요구하는 칸이 어휘에 없으면 선택 규칙 검증이 막히므로, 칸의 이름과 뜻을
# 어휘 쪽에 먼저 등재해 둔다. 어휘는 더해지기만 하고 지워지지 않는다 —
# 이미 저장된 claim이 가리키는 이름이 사라지면 그 claim을 읽을 수 없다.
_VOC_SEED = ExtractionVocabulary(
    entity_type_entries=(
        EntityTypeEntry(
            name="feature_request",
            definition="고객이 요구한 기능 변경 하나를 가리킨다.",
            identity_scope="standalone",
            examples=("다크 모드 지원", "CSV 내보내기"),
        ),
        EntityTypeEntry(
            name="customer",
            definition="요구를 낸 고객사나 고객 계정을 가리킨다.",
            identity_scope="anchored",
        ),
        EntityTypeEntry(
            name="product_area",
            definition="제품을 나누는 기능 영역을 가리킨다.",
            identity_scope="standalone",
        ),
        EntityTypeEntry(
            name="complaint_topic",
            definition="반복해서 제기되는 불만의 주제를 가리킨다.",
            identity_scope="standalone",
        ),
        EntityTypeEntry(
            name="faq_question",
            definition="반복해서 들어오는 고객 질문 하나를 가리킨다.",
            identity_scope="standalone",
        ),
    ),
    predicate_entries=(
        PredicateEntry(
            name="request_status",
            definition=(
                "기능 요구가 어느 처리 단계에 있는지를 나타낸다."
                " collected(수집됨)·under_review(검토중)·confirmed(확정)·"
                "shipped(반영됨)·on_hold(보류)."
            ),
            domain=("feature_request",),
            value_type="enum",
            enum_values=(
                "collected",
                "under_review",
                "confirmed",
                "shipped",
                "on_hold",
            ),
        ),
        PredicateEntry(
            name="request_priority",
            definition="기능 요구의 처리 우선도를 나타낸다.",
            domain=("feature_request",),
            value_type="enum",
            enum_values=("low", "medium", "high", "urgent"),
        ),
        PredicateEntry(
            name="request_count",
            definition="같은 요구가 접수된 횟수를 나타낸다.",
            domain=("feature_request",),
            value_type="number",
        ),
        PredicateEntry(
            name="first_reported_at",
            definition="그 요구나 불만이 처음 접수된 날짜를 나타낸다.",
            domain=("feature_request", "complaint_topic"),
            value_type="date",
        ),
        PredicateEntry(
            name="last_reported_at",
            definition="같은 요구가 마지막으로 접수된 날짜를 나타낸다.",
            domain=("feature_request",),
            value_type="date",
        ),
        PredicateEntry(
            name="usage_context",
            definition="그 요구가 필요한 업무 장면을 나타낸다.",
            domain=("feature_request",),
            value_type="text",
        ),
        PredicateEntry(
            name="requester_role",
            definition="요구를 낸 사람의 역할을 나타낸다(예: CS 리더, AM).",
            domain=("feature_request",),
            value_type="text",
        ),
        PredicateEntry(
            name="frequency",
            definition="그 장면이 얼마나 자주 있는지를 나타낸다(매일·매주·월말).",
            domain=("feature_request",),
            value_type="text",
        ),
        PredicateEntry(
            name="support_status",
            definition=(
                "지금 제품이 그 요구를 어디까지 감당하는지를 나타낸다."
                " supported(지원)·partial(부분 지원)·unsupported(미지원)."
            ),
            domain=("feature_request", "customer"),
            value_type="enum",
            enum_values=("supported", "partial", "unsupported"),
        ),
        PredicateEntry(
            name="workaround",
            definition="승인된 우회 방법이나 대안 단계를 나타낸다.",
            domain=("feature_request", "faq_question"),
            value_type="text",
        ),
        PredicateEntry(
            name="pain_description",
            definition="고객이 겪은 불편을 서술한 내용을 나타낸다.",
            domain=("feature_request", "complaint_topic"),
            value_type="text",
        ),
        PredicateEntry(
            name="complaint_status",
            definition=(
                "그 불편이 어느 대응 단계에 있는지를 나타낸다."
                " confirmed(확인됨)·discussing(대응 논의중)·"
                "resolved(해소됨)·on_hold(보류)."
            ),
            domain=("complaint_topic",),
            value_type="enum",
            enum_values=("confirmed", "discussing", "resolved", "on_hold"),
        ),
        PredicateEntry(
            name="expected_behavior",
            definition="고객이 기대했던 동작이나 결과를 나타낸다.",
            domain=("complaint_topic",),
            value_type="text",
        ),
        PredicateEntry(
            name="reproduction_steps",
            definition=(
                "어떤 상태에서 어떤 행동을 하면 어떤 결과가 나오는지를 나타낸다."
            ),
            domain=("complaint_topic",),
            value_type="text",
        ),
        PredicateEntry(
            name="impact",
            definition="이 문제로 실제 발생하는 관찰된 결과를 나타낸다.",
            domain=("complaint_topic",),
            value_type="text",
        ),
        PredicateEntry(
            name="guidance",
            definition="문의가 들어왔을 때의 승인된 안내 기준을 나타낸다.",
            domain=("complaint_topic",),
            value_type="text",
        ),
        PredicateEntry(
            name="faq_status",
            definition=(
                "그 질문의 답이 확정됐는지를 나타낸다."
                " answer_confirmed(답변 확정)·needs_check(기준 확인 필요)."
            ),
            domain=("faq_question",),
            value_type="enum",
            enum_values=("answer_confirmed", "needs_check"),
        ),
        PredicateEntry(
            name="faq_category",
            definition=(
                "그 질문이 어느 갈래인지를 나타낸다."
                " pricing(요금)·data(데이터)·account(계정)·"
                "integration(연동)."
            ),
            domain=("faq_question",),
            value_type="enum",
            enum_values=("pricing", "data", "account", "integration"),
        ),
        PredicateEntry(
            name="current_answer",
            definition="고객에게 그대로 보낼 수 있는 현재 기준 답변을 나타낸다.",
            domain=("faq_question",),
            value_type="text",
        ),
        PredicateEntry(
            name="internal_notes",
            definition="실무자만 알아야 할 예외·주의사항을 나타낸다.",
            domain=("faq_question",),
            value_type="text",
        ),
        PredicateEntry(
            name="last_confirmed_at",
            definition="이 답이 유효한지 마지막으로 확인된 날을 나타낸다.",
            domain=("faq_question",),
            value_type="date",
        ),
        PredicateEntry(
            name="industry",
            definition="고객사의 업종을 나타낸다.",
            domain=("customer",),
            value_type="text",
        ),
        PredicateEntry(
            name="company_size",
            definition="고객사의 규모를 나타낸다.",
            domain=("customer",),
            value_type="text",
        ),
        PredicateEntry(
            name="adopted_at",
            definition="그 고객사의 제품 도입 시기를 나타낸다.",
            domain=("customer",),
            value_type="date",
        ),
        PredicateEntry(
            name="usage_pattern",
            definition="제품을 어떤 업무 흐름에서 쓰는지를 나타낸다.",
            domain=("customer",),
            value_type="text",
        ),
        PredicateEntry(
            name="account_request_status",
            definition=(
                "그 고객사가 낸 요청이 어느 단계에 있는지를 나타낸다."
                " received(접수)·under_review(검토중)·answered(답변 완료)·"
                "shipped(반영됨)·declined(거절)."
            ),
            domain=("customer",),
            value_type="enum",
            enum_values=(
                "received",
                "under_review",
                "answered",
                "shipped",
                "declined",
            ),
        ),
        PredicateEntry(
            name="churn_risk",
            definition="이 고객이 이탈 위험으로 표시됐는지를 나타낸다.",
            domain=("customer",),
            value_type="boolean",
        ),
    ),
    relation_type_entries=(
        RelationTypeEntry(
            name="requested_by",
            definition="그 기능 요구를 낸 고객을 잇는다.",
            domain=("feature_request",),
            range_=("customer",),
        ),
        RelationTypeEntry(
            name="belongs_to_area",
            definition="그 요구가 속한 제품 영역을 잇는다.",
            domain=("feature_request",),
            range_=("product_area",),
        ),
        RelationTypeEntry(
            name="duplicates",
            definition="같은 내용을 가리키는 다른 요구를 잇는다.",
            domain=("feature_request",),
            range_=("feature_request",),
        ),
        RelationTypeEntry(
            name="complains_about",
            definition="그 고객이 제기한 불만 주제를 잇는다.",
            domain=("customer",),
            range_=("complaint_topic",),
        ),
        RelationTypeEntry(
            name="related_question",
            definition="함께 자주 묻는 다른 질문을 잇는다.",
            domain=("faq_question",),
            range_=("faq_question",),
        ),
    ),
)


def _feature_request_status_spec() -> SelectionSpec:
    """기능 요구 하나를 현황 문서 한 편으로 잡는 규칙을 만든다."""
    return SelectionSpec(
        entity_types=("feature_request",),
        relation_paths=(
            RelationPath(steps=(RelationStep("requested_by", DIRECTION_OUT),)),
            RelationPath(
                steps=(RelationStep("belongs_to_area", DIRECTION_OUT),)
            ),
        ),
        predicate_sections=(
            "request_status",
            "request_priority",
            "first_reported_at",
        ),
    )


def _request_priority_board_spec() -> SelectionSpec:
    """기능 요구를 우선순위 관점으로 모으는 규칙을 만든다."""
    return SelectionSpec(
        entity_types=("feature_request",),
        relation_paths=(
            RelationPath(steps=(RelationStep("requested_by", DIRECTION_OUT),)),
        ),
        predicate_sections=("request_priority", "request_count"),
    )


def _customer_voice_profile_spec() -> SelectionSpec:
    """고객 한 곳이 낸 목소리를 한 편으로 모으는 규칙을 만든다."""
    return SelectionSpec(
        entity_types=("customer",),
        relation_paths=(
            RelationPath(steps=(RelationStep("requested_by", DIRECTION_IN),)),
            RelationPath(
                steps=(RelationStep("complains_about", DIRECTION_OUT),)
            ),
        ),
        predicate_sections=("churn_risk",),
    )


def _product_area_digest_spec() -> SelectionSpec:
    """제품 영역별로 요구를 묶어 보는 규칙을 만든다.

    섹션을 고르지 않는다(None) — 영역 문서는 claim을 추려 담기보다
    어떤 요구가 이 영역에 붙어 있는지를 보여 주는 쪽이다.
    """
    return SelectionSpec(
        entity_types=("product_area",),
        relation_paths=(
            RelationPath(
                steps=(RelationStep("belongs_to_area", DIRECTION_IN),)
            ),
        ),
        predicate_sections=None,
    )


def _complaint_topic_brief_spec() -> SelectionSpec:
    """불만 주제 하나를 짧은 브리프로 잡는 규칙을 만든다."""
    return SelectionSpec(
        entity_types=("complaint_topic",),
        relation_paths=(
            RelationPath(
                steps=(RelationStep("complains_about", DIRECTION_IN),)
            ),
        ),
        predicate_sections=("first_reported_at", "pain_description"),
    )


def _churn_risk_watch_spec() -> SelectionSpec:
    """불만을 제기한 고객을 모아 이탈 위험 표시를 함께 보여주는 규칙을
    만든다."""
    return SelectionSpec(
        entity_types=("customer",),
        relation_paths=(
            RelationPath(
                steps=(RelationStep("complains_about", DIRECTION_OUT),)
            ),
        ),
        predicate_sections=("churn_risk",),
    )


_VOC_KINDS = (
    PresetKind(
        kind="feature_request_status",
        label="기능 요구 현황",
        description="요구 하나가 지금 어느 단계에 있는지 정리한 문서다.",
        example_text=(
            "다크 모드 지원 — 상태 in_progress, 우선도 high, 최초 접수 2026-01-12."
        ),
        spec_template=_feature_request_status_spec,
    ),
    PresetKind(
        kind="request_priority_board",
        label="요구 우선순위 보드",
        description="어떤 요구를 먼저 볼지 우선도와 접수 횟수로 늘어놓는다.",
        example_text="CSV 내보내기 — 우선도 urgent, 접수 17건.",
        spec_template=_request_priority_board_spec,
    ),
    PresetKind(
        kind="customer_voice_profile",
        label="고객 목소리 프로필",
        description="고객 한 곳이 낸 요구와 불만을 한 편에 모은 문서다.",
        example_text="A사 — 요구 4건(다크 모드 외), 불만 주제 2건, 이탈 위험 표시.",
        spec_template=_customer_voice_profile_spec,
    ),
    PresetKind(
        kind="product_area_digest",
        label="제품 영역 요약",
        description="한 기능 영역에 붙은 요구들을 모아 보여 주는 문서다.",
        example_text="내보내기 영역 — 관련 요구 9건.",
        spec_template=_product_area_digest_spec,
    ),
    PresetKind(
        kind="complaint_topic_brief",
        label="불만 주제 브리프",
        description="반복되는 불만 하나를 짧게 요약한 문서다.",
        example_text="로그인 지연 — 최초 접수 2025-11-03, 대기 시간이 길다는 불편.",
        spec_template=_complaint_topic_brief_spec,
    ),
    PresetKind(
        kind="churn_risk_watch",
        label="이탈 위험 관찰",
        description=(
            "불만을 제기한 고객을 모아 각 고객의 이탈 위험 표시를 함께"
            " 보여주는 문서다."
        ),
        example_text="B사 — 불만 주제 3건, 이탈 위험 표시 true.",
        spec_template=_churn_risk_watch_spec,
    ),
)


_VOC_PURPOSES = (
    PresetPurpose(
        id="voc.top_requests",
        label="많이 들어온 요구 보기",
        recommended_kind="request_priority_board",
    ),
    PresetPurpose(
        id="voc.request_status_tracking",
        label="요구 처리 현황 따라가기",
        recommended_kind="feature_request_status",
    ),
    PresetPurpose(
        id="voc.customer_understanding",
        label="고객을 더 알기",
        recommended_kind="customer_voice_profile",
    ),
    PresetPurpose(
        id="voc.complaint_patterns",
        label="반복되는 불만 찾기",
        recommended_kind="complaint_topic_brief",
    ),
    PresetPurpose(
        id="voc.churn_signals",
        label="이탈 신호 살피기",
        recommended_kind="churn_risk_watch",
    ),
)


PRESET_DOMAINS: tuple[PresetDomain, ...] = (
    PresetDomain(
        id="voc",
        label="고객 소리(VOC)",
        purposes=_VOC_PURPOSES,
        kinds=_VOC_KINDS,
        seed_vocabulary=_VOC_SEED,
        actor_exposure=EXPOSURE_NAME_EMAIL,
    ),
    PresetDomain(
        id="product",
        label="제품과 기획",
        purposes=(),
        kinds=(),
        seed_vocabulary=ExtractionVocabulary(),
    ),
    PresetDomain(
        id="ops",
        label="운영과 정책",
        purposes=(),
        kinds=(),
        seed_vocabulary=ExtractionVocabulary(),
    ),
    PresetDomain(
        id="sales",
        label="세일즈와 고객",
        purposes=(),
        kinds=(),
        seed_vocabulary=ExtractionVocabulary(),
    ),
    PresetDomain(
        id="dev",
        label="개발과 기술",
        purposes=(),
        kinds=(),
        seed_vocabulary=ExtractionVocabulary(),
    ),
    PresetDomain(
        id="onboarding",
        label="팀 가이드/온보딩",
        purposes=(),
        kinds=(),
        seed_vocabulary=ExtractionVocabulary(),
    ),
)


PRESET_STYLES: tuple[PresetStyle, ...] = (
    PresetStyle(
        id="style.report_summary",
        label="보고서 요약체",
        instruction=(
            "사내 보고서의 요약 문단처럼 쓴다. 사실을 앞에 놓고 평서형"
            " 종결(~이다·~한다)로 끝맺으며, 감탄과 권유를 쓰지 않는다."
            " 수식어보다 값과 상태를 먼저 적는다."
        ),
    ),
    PresetStyle(
        id="style.conversational_brief",
        label="대화체 브리핑",
        instruction=(
            "동료에게 구두로 브리핑하듯 쓴다. 경어체(~습니다)를 쓰고"
            " 문장을 짧게 끊으며, 어려운 말 대신 쉬운 말을 고른다."
            " 다만 친근함을 위해 없는 내용을 덧붙이지 않는다."
        ),
    ),
    PresetStyle(
        id="style.decision_log",
        label="결정 기록체",
        instruction=(
            "결정 기록장에 남기듯 쓴다. 무엇이 정해졌고 무엇이 아직"
            " 열려 있는지를 시간 순서대로 평서형으로 적는다. 근거에"
            " 없는 결정 이유를 지어내지 않는다."
        ),
    ),
    PresetStyle(
        id="style.faq",
        label="FAQ 문답체",
        instruction=(
            "자주 묻는 질문의 답변처럼 쓴다. 읽는 사람이 궁금해할 것을"
            " 먼저 답으로 내놓고 경어체(~습니다)로 끝맺는다. 질문"
            " 문장을 따로 만들지 않고 답변 문단만 쓴다."
        ),
    ),
    PresetStyle(
        id="style.custom",
        label="직접 지정",
        instruction=(
            "특별한 문체 지정이 없다. 평서형 종결(~이다·~한다)로 담백하게"
            " 쓰고, 근거에 있는 사실만 순서대로 적는다."
        ),
    ),
)


# 채널에 문체가 걸려 있지 않거나 카탈로그 밖 id일 때 쓰는 지시문이다.
DEFAULT_STYLE_INSTRUCTION = (
    "평서형 종결(~이다·~한다)로 담백하게 쓴다. 근거에 있는 사실만"
    " 순서대로 적고, 꾸미는 말을 더하지 않는다."
)

# 목적이 없거나 카탈로그 밖 목적일 때 쓰는 행위자 노출 수준이다.
DEFAULT_ACTOR_EXPOSURE = EXPOSURE_NAME

# 카탈로그 밖 kind로 만들어진 문서에 쓰는 목적 문장이다.
DEFAULT_PURPOSE_SENTENCE = (
    "이 문서는 이 대상에 대해 지금까지 확인된 사실을 모아 두는 데 쓴다."
)


def find_purpose(purpose_id: str) -> tuple[PresetDomain, PresetPurpose] | None:
    """목적 id로 그 목적과 소속 도메인을 함께 찾는다.

    목적 id는 도메인 접두를 달고 있지만 접두를 잘라 쓰지 않는다. 카탈로그
    안에 실제로 있는 값만 통과시켜야 모르는 id가 조용히 지나가지 않는다.
    """
    for domain in PRESET_DOMAINS:
        for purpose in domain.purposes:
            if purpose.id == purpose_id:
                return domain, purpose
    return None


def find_kind(domain: PresetDomain, kind: str) -> PresetKind | None:
    """도메인 안에서 문서 종류를 찾는다.

    다른 도메인의 kind는 찾지 않는다. 종류는 그 도메인의 seed 어휘를
    전제로 만들어져 있어, 어휘가 다른 도메인에 붙이면 검증이 깨진다.
    """
    for preset_kind in domain.kinds:
        if preset_kind.kind == kind:
            return preset_kind
    return None


def find_kind_by_name(kind: str) -> PresetKind | None:
    """도메인을 모른 채 문서 종류를 찾는다.

    `find_kind`와 뜻이 다르다. 저쪽은 "이 도메인에서 고를 수 있는가"를
    묻는 온보딩의 관문이고, 이쪽은 이미 저장된 정의의 kind가 카탈로그의
    어느 종류였는지를 되짚는 조회다. 같은 이름이 두 도메인에 걸리지
    않도록 카탈로그가 kind 전역 유일을 지킨다.
    """
    for domain in PRESET_DOMAINS:
        for preset_kind in domain.kinds:
            if preset_kind.kind == kind:
                return preset_kind
    return None


def find_style(style_id: str) -> PresetStyle | None:
    """문체 id로 문체 preset을 찾는다."""
    for style in PRESET_STYLES:
        if style.id == style_id:
            return style
    return None


def find_actor_exposure(purpose_id: str | None) -> str:
    """목적 id로 그 문서가 행위자를 드러낼 수준을 정한다.

    노출 수준은 도메인이 정하고 목적은 도메인을 가리키는 손잡이일
    뿐이다. 목적이 없거나 카탈로그 밖 id면 기본값으로 떨어진다 —
    모르는 목적에 더 넓은 수준을 주면 이메일이 조용히 새어 나간다.
    """
    if purpose_id is None:
        return DEFAULT_ACTOR_EXPOSURE
    found = find_purpose(purpose_id)
    if found is None:
        return DEFAULT_ACTOR_EXPOSURE
    domain, _ = found
    return domain.actor_exposure
