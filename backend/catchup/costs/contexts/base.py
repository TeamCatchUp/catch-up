"""
토큰 사용량 추적을 위한 기본 Context 클래스.

파이프라인별 Context는 이 클래스를 상속하여 구현한다.
- ChatTokenUsageContext: 채팅 파이프라인
- (TODO)IngestionTokenUsageContext: 문서 수집 파이프라인
"""

from collections import defaultdict
from contextvars import ContextVar
from typing import ClassVar
from typing import Self


class BaseTokenUsageContext:
    
    # 클래스 변수
    _current: ClassVar[ContextVar]
    
    def __init__(self):
        # dict[model, dict[input/output, token usage amount]]
        self.token_breakdown: defaultdict[str, defaultdict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        # e.g)
        # {
        #   "arn:aws:bedrock:ap-northeast-2:...:foundation-model/anthropic.claude-haiku-4-5-20251001-v1:0": 
        #   {
        #       "input_tokens": 1200,
        #       "output_tokens": 300,
        #       "cache_read_tokens": 0,
        #       "cache_write_tokens": 0,
        #   }
        # }

    def add_tokens(
        self,
        token_breakdown: dict[str, dict[str, int]]
    ) -> None:
        for model, usage in token_breakdown.items():
            self.token_breakdown[model]["input_tokens"] += usage.get("input_tokens", 0)
            self.token_breakdown[model]["output_tokens"] += usage.get("output_tokens", 0)
            self.token_breakdown[model]["cache_read_tokens"] += usage.get("cache_read_tokens", 0)
            self.token_breakdown[model]["cache_write_tokens"] += usage.get("cache_write_tokens", 0)
    
    @classmethod
    def init(cls) -> Self:
        ctx = cls()
        cls._current.set(ctx)
        return ctx

    @classmethod
    def get(cls) -> Self | None:
        return cls._current.get()
