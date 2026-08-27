"""온보딩이 고르게 할 preset 카탈로그를 담는다.

채널을 만들 때 사용자는 도메인·목적·문체를 고르고, 그 선택이 어떤
어휘와 어떤 선택 규칙으로 풀릴지는 이 카탈로그가 정한다. 값은 전부
상수이고 조회는 순수 함수다 — 같은 선택이면 언제나 같은 결과가
나와야 하기 때문이다.

지금은 VOC(고객 소리) 도메인만 콘텐츠가 채워져 있고, 나머지 도메인은
구조만 등재해 둔다. 목록에 없는 도메인을 나중에 끼워 넣는 것보다,
빈 채로 자리를 잡아 두는 편이 화면과 저장 값의 모양을 미리 고정한다.

VOC 도메인의 kind는 양식 5종이며 정책과 예외사항은 채널톡 소스 밖이라
두지 않는다. 소스에 없는 것을 양식이 요구하면 채울 근거가 없는 칸이
남고, 그 빈칸은 읽는 사람에게 지식이 없다는 뜻으로 잘못 읽힌다.
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
from catchup.knowledge_maintenance.domain.layout import Layout


@dataclass(frozen=True, slots=True)
class PresetKind:
    """문서 종류 하나의 preset을 표현한다.

    Attributes:
        kind: 아티팩트 정의의 kind 값으로 그대로 실린다. 32자 안이다.
        label: 사용자에게 보여줄 짧은 이름을 나타낸다.
        description: 이 종류가 어떤 문서인지 한 줄로 설명한다.
        example_text: 어떤 문서가 나오는지 보여줄 예시를 담는다.
        spec_template: 인자 없이 선택 규칙을 만들어 주는 함수다.
        layout: 이 종류의 문서를 읽을 때 쓸 순서와 이름을 담는다. 저장된
            블록과 그 순서는 그대로 두고 읽기 화면만 바꾸므로, 레이아웃이
            없으면 블록을 컴파일 순서대로 읽는다.
    """

    kind: str
    label: str
    description: str
    example_text: str
    spec_template: Callable[[], SelectionSpec]
    layout: Layout | None = None


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
    """기능 요청 하나를 문서 한 편으로 잡는 규칙을 만든다.

    접수 횟수(request_count)·우선도(request_priority)는 "많이 들어온
    요구"를 보려는 목적의 근거라 문서 안에 남긴다. 선택 규칙에 없는
    절은 컴파일이 버리므로, 여기서 빠지면 그 목적이 가리킬 숫자가
    문서에 하나도 없게 된다. 나중에 집계 뷰가 생기면 그쪽으로 옮길 수
    있다.
    """
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
            "request_count",
            "first_reported_at",
            "last_reported_at",
            "usage_context",
            "requester_role",
            "frequency",
            "support_status",
            "workaround",
        ),
    )


def _complaint_topic_brief_spec() -> SelectionSpec:
    """불편 주제 하나를 재현 가능한 문서로 잡는 규칙을 만든다."""
    return SelectionSpec(
        entity_types=("complaint_topic",),
        relation_paths=(
            RelationPath(
                steps=(RelationStep("complains_about", DIRECTION_IN),)
            ),
        ),
        predicate_sections=(
            "complaint_status",
            "first_reported_at",
            "pain_description",
            "expected_behavior",
            "reproduction_steps",
            "impact",
            "guidance",
        ),
    )


def _faq_answer_spec() -> SelectionSpec:
    """반복 질문 하나와 그 기준 답변을 한 편으로 잡는 규칙을 만든다."""
    return SelectionSpec(
        entity_types=("faq_question",),
        relation_paths=(
            RelationPath(
                steps=(RelationStep("related_question", DIRECTION_OUT),)
            ),
        ),
        predicate_sections=(
            "faq_status",
            "faq_category",
            "current_answer",
            "workaround",
            "internal_notes",
            "last_confirmed_at",
        ),
    )


def _customer_voice_profile_spec() -> SelectionSpec:
    """고객 한 곳이 낸 요청 조건을 한 편으로 모으는 규칙을 만든다."""
    return SelectionSpec(
        entity_types=("customer",),
        relation_paths=(
            RelationPath(steps=(RelationStep("requested_by", DIRECTION_IN),)),
            RelationPath(
                steps=(RelationStep("complains_about", DIRECTION_OUT),)
            ),
        ),
        predicate_sections=("account_request_status", "support_status"),
    )


def _customer_history_spec() -> SelectionSpec:
    """고객 한 곳과 오간 기록을 한 편으로 모으는 규칙을 만든다.

    고른 칸은 고객사 자체의 배경이다. 오간 요청과 불편은 관계 경로로
    딸려 오므로 여기서 값을 다시 고르지 않는다.
    """
    return SelectionSpec(
        entity_types=("customer",),
        relation_paths=(
            RelationPath(steps=(RelationStep("requested_by", DIRECTION_IN),)),
            RelationPath(
                steps=(RelationStep("complains_about", DIRECTION_OUT),)
            ),
        ),
        predicate_sections=(
            "industry",
            "company_size",
            "adopted_at",
            "usage_pattern",
        ),
    )


# 아래 레이아웃은 기획 양식이 정한 읽기 순서다. section_key는 컴파일이
# 붙이는 블록 heading과 글자 그대로 같아야 한다. 절 블록은 predicate
# 이름이 그대로 heading이고, 관계 블록은 경로의 걸음을
# "relation_type(direction)"으로 이어 붙인 문자열이 heading이다.
_FEATURE_REQUEST_STATUS_LAYOUT = Layout(
    sections=(
        ("request_status", "요청 상태"),
        ("request_priority", "우선순위"),
        ("request_count", "요청 횟수"),
        ("first_reported_at", "최초 보고"),
        ("last_reported_at", "최근 보고"),
        ("usage_context", "사용 상황"),
        ("requester_role", "요청자 역할"),
        ("frequency", "빈도"),
        ("support_status", "지원 상태"),
        ("workaround", "우회 방법"),
        ("requested_by(out)", "요청 고객사"),
        ("belongs_to_area(out)", "기능 영역"),
    ),
    always_show=("request_status", "support_status", "workaround"),
)


_COMPLAINT_TOPIC_BRIEF_LAYOUT = Layout(
    sections=(
        ("complaint_status", "처리 상태"),
        ("first_reported_at", "최초 보고"),
        ("pain_description", "불편 내용"),
        ("expected_behavior", "기대 동작"),
        ("reproduction_steps", "재현 절차"),
        ("impact", "영향"),
        ("guidance", "안내"),
        ("complains_about(in)", "신고 고객사"),
    ),
    always_show=("complaint_status", "guidance"),
)


_FAQ_ANSWER_LAYOUT = Layout(
    sections=(
        ("faq_status", "상태"),
        ("faq_category", "분류"),
        ("current_answer", "현재 답변"),
        ("workaround", "우회 방법"),
        ("internal_notes", "내부 메모"),
        ("last_confirmed_at", "최근 확인"),
        ("related_question(out)", "관련 질문"),
    ),
    always_show=("current_answer", "workaround"),
)


_CUSTOMER_VOICE_PROFILE_LAYOUT = Layout(
    sections=(
        ("account_request_status", "요청 상태"),
        ("support_status", "지원 상태"),
        ("requested_by(in)", "요청한 기능"),
        ("complains_about(out)", "불편 사항"),
    ),
    always_show=("account_request_status",),
)


_CUSTOMER_HISTORY_LAYOUT = Layout(
    sections=(
        ("industry", "산업"),
        ("company_size", "규모"),
        ("adopted_at", "도입 시기"),
        ("usage_pattern", "사용 패턴"),
        ("requested_by(in)", "요청한 기능"),
        ("complains_about(out)", "불편 사항"),
    ),
)


_VOC_KINDS = (
    PresetKind(
        kind="feature_request_status",
        label="기능 요청 문서",
        description=(
            "고객이 원하는 기능과 그 이유, 사용 상황을 하나의 문서로"
            " 모은다. 제목은 기능 명칭이 아니라 원하는 결과 중심이다."
        ),
        example_text=(
            "상담 데이터를 엑셀로 내려받고 싶어요 — 상태 검토중,"
            " 최초 접수 2026-06-02."
        ),
        spec_template=_feature_request_status_spec,
        layout=_FEATURE_REQUEST_STATUS_LAYOUT,
    ),
    PresetKind(
        kind="complaint_topic_brief",
        label="고객 불편사항 문서",
        description=(
            "고객이 어떤 상황에서 불편을 겪는지 재현 가능한 형태로"
            " 모은다. 원인을 단정하지 않는다."
        ),
        example_text=(
            "상담 검색에서 원하는 기록을 찾기 어려워요 — 상태 확인됨,"
            " 최초 보고 2026-05-20."
        ),
        spec_template=_complaint_topic_brief_spec,
        layout=_COMPLAINT_TOPIC_BRIEF_LAYOUT,
    ),
    PresetKind(
        kind="faq_answer",
        label="자주 묻는 질문 문서",
        description=(
            "반복되는 질문과 현재 기준 답변을 모아 누가 답해도 같은 답이"
            " 나오게 한다."
        ),
        example_text=(
            "상담 데이터를 엑셀로 받을 수 있나요? — 답변 확정,"
            " 카테고리 데이터."
        ),
        spec_template=_faq_answer_spec,
        layout=_FAQ_ANSWER_LAYOUT,
    ),
    PresetKind(
        kind="customer_voice_profile",
        label="고객사별 요청사항 문서",
        description=(
            "특정 고객이 요청한 기능과 조건을 그 고객의 맥락과 함께"
            " 모은다. 공통 내용은 전사 문서에, 고유 조건만 여기에 남긴다."
        ),
        example_text=(
            "A사 — 상담 데이터를 주 단위로 자동 전달받고 싶어요,"
            " 상태 검토중."
        ),
        spec_template=_customer_voice_profile_spec,
        layout=_CUSTOMER_VOICE_PROFILE_LAYOUT,
    ),
    PresetKind(
        kind="customer_history",
        label="고객사 히스토리 문서",
        description=(
            "고객과 오간 문의·요청·결정을 시간순으로 한 문서에 모은다."
            " 고객당 1문서다."
        ),
        example_text=(
            "A사 — 업종 SaaS, 도입 2026-03, 요청 4건·불편 2건."
        ),
        spec_template=_customer_history_spec,
        layout=_CUSTOMER_HISTORY_LAYOUT,
    ),
)


_VOC_PURPOSES = (
    PresetPurpose(
        id="voc.request_status_tracking",
        label="요구 처리 현황 따라가기",
        recommended_kind="feature_request_status",
    ),
    PresetPurpose(
        id="voc.top_requests",
        label="많이 들어온 요구 보기",
        recommended_kind="feature_request_status",
    ),
    PresetPurpose(
        id="voc.complaint_patterns",
        label="반복되는 불편 찾기",
        recommended_kind="complaint_topic_brief",
    ),
    PresetPurpose(
        id="voc.customer_understanding",
        label="고객을 더 알기",
        recommended_kind="customer_history",
    ),
    PresetPurpose(
        id="voc.faq_consistency",
        label="누가 답해도 같은 답 하기",
        recommended_kind="faq_answer",
    ),
    PresetPurpose(
        id="voc.account_requests",
        label="고객사별 요청 조건 모으기",
        recommended_kind="customer_voice_profile",
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


# 문체를 고르지 않은 문서가 떨어질 자리다. 위키 표준체와 같은 문자열을
# 쓰는 이유는, 고르지 않은 문서와 표준체를 고른 문서가 같은 모양으로
# 나와야 나중에 문체를 지정해도 산출물이 흔들리지 않기 때문이다.
_WIKI_STANDARD_INSTRUCTION = (
    "중립 서술체로 쓴다. 사실·근거·시점을 앞에 놓고 평서형"
    " 종결(~이다·~한다)로 건조하게 기록한다. 감탄·권유·수식어를"
    " 쓰지 않는다."
)


PRESET_STYLES: tuple[PresetStyle, ...] = (
    PresetStyle(
        id="style.wiki_standard",
        label="위키 표준체",
        instruction=_WIKI_STANDARD_INSTRUCTION,
    ),
    PresetStyle(
        id="style.support_guide",
        label="응대 가이드체",
        instruction=(
            "고객에게 그대로 전달할 수 있는 표현으로 쓴다. 해요체로"
            " 끝맺고, 지금 안내할 수 있는 답과 주의점을 앞에 둔다."
            " 내부 용어와 일정 약속은 넣지 않는다."
        ),
    ),
    PresetStyle(
        id="style.report_summary",
        label="보고 요약체",
        instruction=(
            "두괄식 요약으로 쓴다. 판단에 필요한 규모와 추이를 앞에 놓고"
            " 수치와 상태를 먼저 적으며 평서형 종결(~이다·~한다)로"
            " 끝맺는다. 근거에 없는 수치를 만들지 않는다."
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
DEFAULT_STYLE_INSTRUCTION = _WIKI_STANDARD_INSTRUCTION

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


def layout_for_kind(kind: str) -> Layout | None:
    """문서 종류의 읽기 레이아웃을 찾는다.

    카탈로그 밖 kind이거나 레이아웃을 두지 않은 종류면 None이다. 읽는
    쪽은 None을 받으면 블록을 컴파일 순서대로 보여 준다.
    """
    preset_kind = find_kind_by_name(kind)
    if preset_kind is None:
        return None
    return preset_kind.layout


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
