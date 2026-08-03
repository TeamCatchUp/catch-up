"""LongMemEval 세션 한 건을 Extractor가 읽을 형태로 정규화한다.

벤치마크 어댑터의 레이어 1이다. ChannelTalk normalizer와 같은 자리에 서고
같은 계약을 지킨다. LLM은 개입하지 않으며 같은 입력이면 늘 같은 결과다.

본문 형식도 ChannelTalk v3과 같다. 발화마다 자기 시각을 앞에 붙이고,
어느 구간이 어느 발화인지를 `utterance_spans`로 따로 남긴다.

    [2023-04-10 23:07] user: I switched to a road bike.
    [2023-04-10 23:07] assistant: Nice — how is the commute going?

다른 점은 하나다. LongMemEval 세션은 발화별 시각이 없고 세션 시각 하나만
있다. 그래서 모든 턴이 같은 `at`을 쓴다. 없는 시각을 턴마다 지어내는 것보다
세션 시각 하나로 모두 앵커하는 편이 원본에 충실하다.

화자는 원본의 `user`·`assistant`를 그대로 쓴다. LongMemEval에는 사람 이름이
붙어 있지 않으므로 역할로 바꿔 적을 것이 없다.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from catchup.knowledge_maintenance.domain.observation import UTTERANCE_SPANS_ATTRIBUTE
from catchup.knowledge_maintenance.domain.observation import NormalizedObservation
from catchup.knowledge_maintenance.domain.observation import ObservationKind
from catchup.knowledge_maintenance.domain.observation import content_hash
from catchup.knowledge_maintenance.domain.source_version import JsonValue
from catchup.knowledge_maintenance.domain.source_version import SourceVersion

# SourceVersion.content가 담고 있는 payload의 형식이다. oracle 데이터셋 원본
# 스키마가 아니라 `evaluation.longmemeval`이 세션 하나만 떼어 직렬화한
# 형태다: `{"session_id", "timestamp", "turns": [{"role", "content"}]}`.
LONGMEMEVAL_SESSION_MEDIA_TYPE = "application/vnd.longmemeval.session+json"


class LongMemEvalSessionNormalizer:
    """LongMemEval 세션 한 건을 NormalizedObservation으로 옮긴다."""

    normalizer_id = "longmemeval.session"
    normalizer_version = "1"

    def normalize(
        self, source_version: SourceVersion
    ) -> NormalizedObservation:
        if source_version.content_type != LONGMEMEVAL_SESSION_MEDIA_TYPE:
            raise ValueError(
                "content_type must be "
                f"{LONGMEMEVAL_SESSION_MEDIA_TYPE}, "
                f"got {source_version.content_type}"
            )
        if source_version.content is None:
            raise ValueError("content must not be empty")

        payload = json.loads(source_version.content)
        occurred_at = datetime.fromisoformat(payload["timestamp"])
        turns = payload["turns"]

        content, spans = _render_utterances(turns, occurred_at=occurred_at)
        return NormalizedObservation(
            normalizer_id=self.normalizer_id,
            normalizer_version=self.normalizer_version,
            observation_kind=ObservationKind.DOCUMENT,
            content=content,
            content_hash=content_hash(content),
            source_attributes={
                "session_id": payload["session_id"],
                "turn_count": len(turns),
                UTTERANCE_SPANS_ATTRIBUTE: spans,
            },
            metadata_entities=(),
            occurred_at=occurred_at,
        )


def _render_utterances(
    turns: Sequence[dict[str, Any]],
    *,
    occurred_at: datetime,
) -> tuple[str, list[JsonValue]]:
    """턴 목록으로 본문을 만들고 발화 구간 지도를 함께 낸다.

    구간은 발화 줄 전체(시각 접두사 포함)를 가리키며 offset 단위는
    `domain.evidence.Locator`와 같은 Unicode code point다. claim의 locator를
    이 구간에 그대로 대조할 수 있어야 하기 때문이다.

    턴 본문에 개행이 들어 있는 경우가 흔하다. 원문을 손대지 않고 그대로
    두므로 한 턴이 여러 줄을 차지할 수 있고, 그래서 구간은 줄 번호가 아니라
    code point로만 센다.
    """
    stamp = f"[{occurred_at:%Y-%m-%d %H:%M}] "
    at = occurred_at.isoformat()
    lines: list[str] = []
    spans: list[JsonValue] = []
    offset = 0
    for turn in turns:
        text = (turn.get("content") or "").strip()
        if not text:
            continue
        line = f"{stamp}{turn['role']}: {text}"
        lines.append(line)
        spans.append({"start": offset, "end": offset + len(line), "at": at})
        # 줄 사이 개행 한 칸까지 세어야 다음 발화의 시작이 본문 offset과
        # 맞는다.
        offset += len(line) + 1

    return "\n".join(lines), spans
