from __future__ import annotations

from contextvars import ContextVar
from typing import ClassVar
from typing import Self

from catchup.audit.metadata import BaseAuditMetadata
from catchup.events.enums import BaseEventAction


class AuditContext:
    _current: ClassVar[ContextVar[AuditContext | None]] = ContextVar(
        "current_audit_context", default=None
    )

    def __init__(self):
        self.metadata: BaseAuditMetadata | None = None
        
        # action은 함수 진입 시점에 주입해야 함.
        # (audit/utils.py audit_log 데코레이터 주석 참고)
        self.action: BaseEventAction | None = None

    @classmethod
    def init(cls,) -> Self:
        ctx = cls()
        cls._current.set(ctx)
        return ctx

    @classmethod
    def get(cls) -> Self | None:
        return cls._current.get()
