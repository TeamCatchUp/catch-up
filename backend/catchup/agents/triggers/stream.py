from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from typing import Final
from typing import Mapping

from pydantic import BaseModel

AGENT_RUN_REQUEST_STREAM_KEY: Final[str] = "agent_trigger:run_requests:v1"
AGENT_RUN_REQUEST_CONSUMER_GROUP: Final[str] = "agent-trigger-listeners"
AGENT_RUN_REQUEST_READ_NEW_MESSAGE_ID: Final[str] = ">"
AGENT_RUN_REQUEST_CLAIM_START_ID: Final[str] = "0-0"


class AgentRunRequest(BaseModel):
    """outbox publisher가 worker에게 넘기는 최소 실행 식별자."""

    run_id: int
    trigger_id: int
    agent_spec_id: int
    event_id: str
    policy_kind: str
    dispatch_token: str | None = None

    def to_stream_fields(self) -> dict[str, str]:
        """Redis Stream field는 문자열만 안정적으로 왕복되도록 명시 변환한다."""
        fields = {
            "run_id": str(self.run_id),
            "trigger_id": str(self.trigger_id),
            "agent_spec_id": str(self.agent_spec_id),
            "event_id": self.event_id,
            "policy_kind": self.policy_kind,
        }
        if self.dispatch_token:
            fields["dispatch_token"] = self.dispatch_token
        return fields

    @classmethod
    def from_stream_fields(cls, fields: Mapping[Any, Any]) -> "AgentRunRequest":
        """Redis가 bytes로 돌려주는 field를 Pydantic 입력으로 복원한다."""
        normalized = {_decode(key): _decode(value) for key, value in fields.items()}
        return cls(
            run_id=int(normalized["run_id"]),
            trigger_id=int(normalized["trigger_id"]),
            agent_spec_id=int(normalized["agent_spec_id"]),
            event_id=normalized["event_id"],
            policy_kind=normalized["policy_kind"],
            dispatch_token=normalized.get("dispatch_token") or None,
        )


class AgentRunStreamMessage(BaseModel):
    """malformed 메시지도 ACK 판단 대상이 되도록 원본 message id와 함께 담는다."""

    message_id: str
    request: AgentRunRequest | None = None
    malformed: bool = False
    error: str | None = None


@dataclass(slots=True, frozen=True)
class AckDeleteResult:
    """ACK와 stream delete 결과를 테스트/로그에서 확인하기 위한 값 객체."""

    acked: int
    deleted: int


def decode_agent_run_stream_entries(
    raw_entries: list[tuple[Any, Mapping[Any, Any]]],
) -> list[AgentRunStreamMessage]:
    """Redis Stream 원본을 worker가 ACK 판단 가능한 메시지로 정규화한다.

    malformed 메시지도 버리지 않고 표시해야 listener가 ACK 후 제거할 수 있다.
    """
    messages: list[AgentRunStreamMessage] = []
    for raw_message_id, raw_fields in raw_entries:
        message_id = _decode(raw_message_id)
        try:
            request = AgentRunRequest.from_stream_fields(raw_fields)
            messages.append(
                AgentRunStreamMessage(message_id=message_id, request=request)
            )
        except Exception as exc:
            messages.append(
                AgentRunStreamMessage(
                    message_id=message_id,
                    malformed=True,
                    error=str(exc),
                )
            )
    return messages


def _decode(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)
