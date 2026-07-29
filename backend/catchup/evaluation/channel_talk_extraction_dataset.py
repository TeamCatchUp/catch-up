"""ChannelTalk 합성 상담을 두 가지 정규화로 읽는다.

레이어 1이 실제로 무엇을 바꾸는지 재려면 같은 대화를 두 형태로 넣어 봐야
한다. 이 loader가 그 두 형태를 만든다.

    raw          `experiments/channel_talk/raw/*.txt`를 그대로 쓴다.
                 기존 `contextual_content`를 모방한 형태이며 제목·태그·담당자가
                 본문 줄로 눌러붙어 있다. 레이어 1이 없는 상태다.

    normalized   `experiments/channel_talk/payload/*.json`을 SourceVersion으로
                 감싸 `ChannelTalkUserChatNormalizer`에 통과시킨다.
                 운영에서 Extractor가 받게 될 것과 같은 형태다.

두 형태의 대화 내용은 같다. 달라지는 것은 구조를 걷어냈는지 여부뿐이므로,
추출 결과의 차이는 레이어 1에서 온 것으로 볼 수 있다.

두 디렉토리는 gitignore 대상이다. 없으면 먼저 아래를 돌린다.

    uv run python -m catchup.evaluation.build_channel_talk_payloads

개발과 평가 전용이며 운영 경로가 아니다.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from datetime import timezone
from enum import StrEnum
from pathlib import Path

from catchup.evaluation.llm_wiki_extraction_dataset import ExtractionSource
from catchup.knowledge_maintenance.adapters.channel_talk.observation_normalizer import (
    CHANNEL_TALK_USER_CHAT_MEDIA_TYPE,
)
from catchup.knowledge_maintenance.adapters.channel_talk.observation_normalizer import (
    ChannelTalkUserChatNormalizer,
)
from catchup.knowledge_maintenance.domain.observation import NormalizedObservation
from catchup.knowledge_maintenance.domain.observation import ObservationKind
from catchup.knowledge_maintenance.domain.observation import content_hash
from catchup.knowledge_maintenance.domain.source_version import ChangeKind
from catchup.knowledge_maintenance.domain.source_version import SourceIdentity
from catchup.knowledge_maintenance.domain.source_version import SourceVersion

_EXPERIMENT_DIR = Path(__file__).parent.parent / "experiments" / "channel_talk"
RAW_DIR = _EXPERIMENT_DIR / "raw"
PAYLOAD_DIR = _EXPERIMENT_DIR / "payload"

SOURCE_TYPE = "channel_talk"
CLUSTER_ID = "channel_talk_support"
RAW_NORMALIZER_ID = "evaluation.channel_talk_contextual_content"

# 평가는 DB를 거치지 않으므로 SourceVersion의 시각과 hash는 자리만 채운다.
_PLACEHOLDER_MOMENT = datetime(2026, 7, 28, tzinfo=timezone.utc)
_PLACEHOLDER_HASH = "0" * 64


class ChannelTalkDatasetMode(StrEnum):
    """레이어 1을 통과시킬지 여부를 고른다."""

    RAW = "raw"
    NORMALIZED = "normalized"


def load_channel_talk_sources(
    mode: ChannelTalkDatasetMode,
) -> tuple[ExtractionSource, ...]:
    """합성 상담을 고른 형태로 읽는다."""
    if mode == ChannelTalkDatasetMode.RAW:
        return tuple(_load_raw(path) for path in sorted(RAW_DIR.glob("*.txt")))
    return tuple(_load_normalized(path) for path in sorted(PAYLOAD_DIR.glob("*.json")))


def _load_raw(path: Path) -> ExtractionSource:
    """렌더링된 텍스트를 정규화 없이 그대로 싣는다."""
    content = path.read_text(encoding="utf-8").strip()
    return ExtractionSource(
        key=path.stem,
        document_id=path.stem,
        source_type=SOURCE_TYPE,
        cluster_id=CLUSTER_ID,
        observation=NormalizedObservation(
            normalizer_id=RAW_NORMALIZER_ID,
            normalizer_version="0",
            observation_kind=ObservationKind.DOCUMENT,
            content=content,
            content_hash=content_hash(content),
        ),
    )


def _load_normalized(path: Path) -> ExtractionSource:
    """payload를 SourceVersion으로 감싸 레이어 1에 통과시킨다."""
    normalizer = ChannelTalkUserChatNormalizer()
    source_version = _as_source_version(path)
    return ExtractionSource(
        key=path.stem,
        document_id=path.stem,
        source_type=SOURCE_TYPE,
        cluster_id=CLUSTER_ID,
        observation=normalizer.normalize(source_version),
    )


def _as_source_version(path: Path) -> SourceVersion:
    """payload 파일 하나를 SourceVersion으로 감싼다.

    운영에서는 poller가 만든 SourceChangeEnvelope에서 이 값이 나온다. 여기서는
    normalizer를 부르는 데 필요한 최소한만 채운다.
    """
    key = path.stem
    return SourceVersion(
        id=uuid.uuid5(uuid.NAMESPACE_URL, f"channel-talk-eval/{key}"),
        workspace_id=1,
        source_type=SOURCE_TYPE,
        source_identity=SourceIdentity(
            entity_type="user_chat",
            scope_id="ch-catchup-eval",
            target_id="ch-catchup-eval",
            external_document_id=key,
        ),
        change_kind=ChangeKind.CREATED,
        source_version_key="1",
        title=None,
        canonical_url=None,
        content=path.read_text(encoding="utf-8"),
        content_type=CHANNEL_TALK_USER_CHAT_MEDIA_TYPE,
        content_hash=_PLACEHOLDER_HASH,
        source_updated_at=_PLACEHOLDER_MOMENT,
        observed_at=_PLACEHOLDER_MOMENT,
        idempotency_key=f"{key}-1",
        payload_hash=_PLACEHOLDER_HASH,
        metadata={},
        created_at=_PLACEHOLDER_MOMENT,
    )
