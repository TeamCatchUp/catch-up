from __future__ import annotations

from contextvars import ContextVar
from typing import ClassVar
from typing import Self

from catchup.audit.base import BaseAuditAction
from catchup.audit.metadata import BaseAuditMetadata


class AuditContext:
    _current: ClassVar[ContextVar[AuditContext | None]] = ContextVar(
        "current_audit_context", default=None
    )

    def __init__(self):
        self.metadata: BaseAuditMetadata | None = None
        
        # action은 함수 진입 시점에 주입해야 함.
        # (audit/utils.py audit_log 데코레이터 주석 참고)
        self.action: BaseAuditAction | None = None

    @classmethod
    def init(cls,) -> Self:
        ctx = cls()
        cls._current.set(ctx)
        return ctx

    @classmethod
    def get(cls) -> Self | None:
        return cls._current.get()
    
    @classmethod
    def set_context(cls, context: str) -> None:
        """
        BaseAuditMetadata.context 필드에 서비스 맥락을 주입한다.
        예외 발생 맥락을 기록하는 경우 raise하기 전에 호출한다.
        """
        ctx = cls.get()
        if not ctx:
            return
        
        if not ctx.metadata:
            ctx.metadata = BaseAuditMetadata()
        
        ctx.metadata.context = context
