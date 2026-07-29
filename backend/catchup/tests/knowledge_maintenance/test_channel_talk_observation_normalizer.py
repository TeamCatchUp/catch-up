from __future__ import annotations

import json
import uuid
from datetime import datetime
from datetime import timezone
from pathlib import Path

import pytest

from catchup.knowledge_maintenance.adapters.channel_talk.observation_normalizer import (
    CHANNEL_TALK_USER_CHAT_MEDIA_TYPE,
)
from catchup.knowledge_maintenance.adapters.channel_talk.observation_normalizer import (
    ChannelTalkUserChatNormalizer,
)
from catchup.knowledge_maintenance.domain.observation import ObservationKind
from catchup.knowledge_maintenance.domain.observation import content_hash
from catchup.knowledge_maintenance.domain.source_version import ChangeKind
from catchup.knowledge_maintenance.domain.source_version import SourceIdentity
from catchup.knowledge_maintenance.domain.source_version import SourceVersion

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "channel_talk"
NOW = datetime(2026, 7, 28, 9, 0, tzinfo=timezone.utc)

# 008 봇·입력폼 안내·버튼·담당자 / 011 입력폼 제출
# 013 내부 대화 / 014 첨부 파일 두 건
BOT_AND_BUTTON = "ct-eval-008"
SUBMITTED_FORM = "ct-eval-011"
INTERNAL_MESSAGE = "ct-eval-013"
ATTACHMENTS = "ct-eval-014"

# 정규화된 본문에서 화자를 가리키는 이름이다.
_SPEAKER_PREFIXES = ("고객:", "상담원:", "봇:", "[내부] 상담원:", "[내부] 봇:")


def _payload(key: str) -> str:
    return (FIXTURE_DIR / f"{key}.json").read_text(encoding="utf-8")


def _source_version(key: str, **overrides: object) -> SourceVersion:
    values: dict[str, object] = {
        "id": uuid.UUID("00000000-0000-0000-0000-000000000001"),
        "workspace_id": 1,
        "source_type": "channel_talk",
        "source_identity": SourceIdentity(
            entity_type="user_chat",
            scope_id="ch-catchup-eval",
            target_id="ch-catchup-eval",
            external_document_id=key,
        ),
        "change_kind": ChangeKind.CREATED,
        "source_version_key": "1",
        "title": None,
        "canonical_url": None,
        "content": _payload(key),
        "content_type": CHANNEL_TALK_USER_CHAT_MEDIA_TYPE,
        "content_hash": "a" * 64,
        "source_updated_at": NOW,
        "observed_at": NOW,
        "idempotency_key": f"{key}-1",
        "payload_hash": "b" * 64,
        "metadata": {},
        "created_at": NOW,
    }
    values.update(overrides)
    return SourceVersion(**values)  # type: ignore[arg-type]


@pytest.fixture
def normalizer() -> ChannelTalkUserChatNormalizer:
    return ChannelTalkUserChatNormalizer()


def test_every_content_line_is_an_utterance(normalizer) -> None:
    """본문에는 발화만 남고 머리말과 상태 기록은 빠진다."""
    observation = normalizer.normalize(_source_version(BOT_AND_BUTTON))

    lines = observation.content.splitlines()
    assert lines
    for line in lines:
        assert line.startswith(_SPEAKER_PREFIXES), line


def test_chat_title_is_not_in_content(normalizer) -> None:
    """제목은 원문 필드이므로 본문에 섞이지 않는다."""
    observation = normalizer.normalize(_source_version(BOT_AND_BUTTON))

    assert "요금 산정 기준 문의" not in observation.content
    assert observation.source_attributes["title"] == "요금 산정 기준 문의"


def test_lifecycle_logs_leave_content_and_stay_in_attributes(normalizer) -> None:
    """open·assign·close는 발화가 아니라 상태 기록이다."""
    observation = normalizer.normalize(_source_version(BOT_AND_BUTTON))

    actions = [entry["action"] for entry in observation.source_attributes["lifecycle"]]
    assert actions == ["open", "assign", "close"]
    for action in actions:
        assert f": {action}" not in observation.content


def test_tags_go_to_attributes(normalizer) -> None:
    """태그는 사람이 붙인 분류이므로 본문 밖에 둔다."""
    observation = normalizer.normalize(_source_version(BOT_AND_BUTTON))

    assert observation.source_attributes["tags"] == ["요금", "도입"]
    assert observation.source_attributes["state"] == "closed"


def test_participants_become_metadata_entities(normalizer) -> None:
    """고객과 상담원은 외부 ID를 가진 확정된 대상이다."""
    observation = normalizer.normalize(_source_version(BOT_AND_BUTTON))

    by_type = {
        entity.entity_type: entity for entity in observation.metadata_entities
    }
    assert set(by_type) == {"channel_talk_user", "channel_talk_manager"}

    customer = by_type["channel_talk_user"]
    assert customer.display_name == "사용자 008"
    assert customer.external_key is not None

    manager = by_type["channel_talk_manager"]
    assert manager.display_name == "Catch Up - 캐치업"
    assert manager.attributes["is_assignee"] is True


def test_bot_is_not_a_metadata_entity(normalizer) -> None:
    """봇은 지식의 주체가 아니므로 Entity로 올리지 않는다."""
    observation = normalizer.normalize(_source_version(BOT_AND_BUTTON))

    names = {entity.display_name for entity in observation.metadata_entities}
    assert "Catch Up | 캐치업" not in names
    # 다만 봇이 말한 사실 자체는 본문에 남는다.
    assert "봇: " in observation.content


def test_private_message_is_kept_and_marked(normalizer) -> None:
    """내부 대화에도 지식이 있으나 공개 발화와 구분해야 한다."""
    observation = normalizer.normalize(_source_version(INTERNAL_MESSAGE))

    assert "[내부] 상담원: 권한 축소 후 기존 색인 제거 상태 확인 요청" in (
        observation.content
    )
    assert observation.source_attributes["message_counts"]["private"] == 1


def test_submitted_form_goes_to_attributes_not_content(normalizer) -> None:
    """입력폼 제출값은 구조화된 데이터이지 발화가 아니다."""
    observation = normalizer.normalize(_source_version(SUBMITTED_FORM))

    assert observation.source_attributes["form_submissions"] == [
        {"label": "회사명", "value": "예시테크"},
        {"label": "검토 일정", "value": "다음 달 초"},
    ]
    assert "예시테크" not in observation.content


def test_attachment_names_go_to_attributes(normalizer) -> None:
    """파일명은 상태값이고 본문에는 첨부했다는 사실만 남는다."""
    observation = normalizer.normalize(_source_version(ATTACHMENTS))

    names = [item["name"] for item in observation.source_attributes["attachments"]]
    assert names == ["confluence-space-setting.png", "catchup-member-setting.png"]
    assert "confluence-space-setting.png" not in observation.content
    assert observation.content.count("고객: [파일 첨부]") == 2


def test_button_label_goes_to_attributes(normalizer) -> None:
    """버튼은 화면 요소이므로 발화에서 뺀다.

    같은 메시지의 본문("도입 상담 신청")은 상담원이 실제로 한 말이므로
    남고, 버튼에 적힌 라벨만 상태값으로 빠진다.
    """
    observation = normalizer.normalize(_source_version(BOT_AND_BUTTON))

    assert observation.source_attributes["buttons"] == ["상담 신청"]
    assert "상담원: 도입 상담 신청" in observation.content
    assert "버튼" not in observation.content


def test_occurred_at_is_when_the_chat_opened(normalizer) -> None:
    """상담이 일어난 시각은 열린 시각이다."""
    observation = normalizer.normalize(_source_version(BOT_AND_BUTTON))

    assert observation.occurred_at == datetime(
        2026, 6, 9, 9, 0, tzinfo=timezone.utc
    )


def test_content_hash_matches_content(normalizer) -> None:
    observation = normalizer.normalize(_source_version(BOT_AND_BUTTON))

    assert observation.content_hash == content_hash(observation.content)


def test_deleted_source_version_becomes_a_tombstone(normalizer) -> None:
    """삭제는 행을 지우지 않고 본문 없는 관찰로 남긴다."""
    source_version = _source_version(
        BOT_AND_BUTTON,
        change_kind=ChangeKind.DELETED,
        content=None,
        content_type=None,
    )

    observation = normalizer.normalize(source_version)

    assert observation.observation_kind == ObservationKind.TOMBSTONE
    assert observation.content is None
    assert observation.metadata_entities == ()


def test_unknown_content_type_is_rejected(normalizer) -> None:
    """정규화 계약이 다루지 못하는 형식을 조용히 넘기지 않는다."""
    source_version = _source_version(BOT_AND_BUTTON, content_type="text/markdown")

    with pytest.raises(ValueError, match="content_type"):
        normalizer.normalize(source_version)


def test_normalizing_twice_gives_the_same_result(normalizer) -> None:
    """LLM이 개입하지 않으므로 결과가 흔들리지 않는다."""
    source_version = _source_version(ATTACHMENTS)

    first = normalizer.normalize(source_version)
    second = normalizer.normalize(source_version)

    assert first == second


def test_normalizer_identity_is_declared(normalizer) -> None:
    """Observation은 어느 계약으로 만들어졌는지 스스로 밝혀야 한다."""
    observation = normalizer.normalize(_source_version(BOT_AND_BUTTON))

    assert observation.normalizer_id == normalizer.normalizer_id
    assert observation.normalizer_version == normalizer.normalizer_version


def test_source_attributes_are_json_serializable(normalizer) -> None:
    """상태값은 JSONB 컬럼에 그대로 들어가야 한다."""
    observation = normalizer.normalize(_source_version(BOT_AND_BUTTON))

    json.dumps(dict(observation.source_attributes))
