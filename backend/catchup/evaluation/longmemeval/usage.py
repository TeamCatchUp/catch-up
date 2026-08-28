"""Bedrock 응답에서 토큰 집계와 본문을 읽어 내는 자리를 하나로 둔다.

LLM을 부르는 평가 쪽 모듈 넷 — 어휘 초안·QA·채점 러너와 그중 QA 러너가
쓰는 `qa_service` — 이 같은 두 가지를 묻는다. 이 호출이 토큰을 얼마나
썼는가, 그리고 사람이 읽을 본문은 어디인가. 모듈마다 복붙해 두면 한쪽만
고친 순간 같은 실행의 비용이 파일마다 달라진다.

`UsageTotals`가 비용 계측의 단위다. 러너는 이 값을 더해 가며 실행 하나의
총량을 만들고, 채점 리포트가 그 값에 단가를 곱한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

__all__ = [
    "UsageTotals",
    "message_text",
    "usage_from_message",
]


@dataclass(frozen=True)
class UsageTotals:
    """LLM 호출이 쓴 토큰을 합산한다."""

    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        """입력과 출력 토큰을 합친 수를 나타낸다."""
        return self.input_tokens + self.output_tokens

    def plus(self, other: UsageTotals) -> UsageTotals:
        """다른 집계를 더한 새 집계를 만든다."""
        return UsageTotals(
            calls=self.calls + other.calls,
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
        )

    def as_dict(self) -> dict[str, int]:
        """비용 계측 파일에 담을 형태로 바꾼다."""
        return {
            "calls": self.calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
        }


def usage_from_message(message: Any) -> UsageTotals:
    """응답 메시지의 usage_metadata를 사용량 집계로 옮긴다.

    구조화 출력을 쓰면 파싱된 모델에는 토큰 수가 남지 않는다. 그래서
    `include_raw=True`로 받은 원본 메시지에서 읽는다. 메타데이터가 아예
    없더라도 호출은 있었으므로 호출 수는 센다.
    """
    metadata = getattr(message, "usage_metadata", None) or {}
    return UsageTotals(
        calls=1,
        input_tokens=int(metadata.get("input_tokens") or 0),
        output_tokens=int(metadata.get("output_tokens") or 0),
    )


def message_text(message: Any) -> str:
    """모델 응답에서 사람이 읽을 본문만 뽑는다.

    Bedrock은 content를 문자열로도 블록 리스트로도 돌려준다. 리스트를
    그대로 문자열로 만들면 답변이나 판정의 첫 단어가 본문이 아니라 JSON
    껍데기가 된다.
    """
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = [
            str(block.get("text", ""))
            for block in content
            if isinstance(block, dict) and block.get("type", "text") == "text"
        ]
        return "".join(parts).strip()
    return str(content).strip()
