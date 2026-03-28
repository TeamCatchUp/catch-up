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
    
    @classmethod
    def set_context(cls, context: str) -> None:
        """
        BaseAuditMetadata.context 필드에 서비스 맥락을 주입한다.
        예외 발생 맥락을 기록하는 경우 raise하기 전에 호출한다.
        """
        ctx = cls.get()
        if not ctx:
            return
        if ctx.metadata:
            ctx.metadata.context = context
        else:
            ctx.metadata = BaseAuditMetadata(context=context)

    @classmethod
    def set_error(cls, error: Exception) -> None:
        """
        예외 발생 시 감사 로그에 error_type과 context를 주입한다.
        raise 전에 호출한다.

        Args:
            error: 발생한 예외 객체.
                커스텀 도메인 예외의 code를 context로 자동 추출한다.

        Examples:
            except UserError as e:
                AuditContext.set_error(e)
                raise
        """        
        ctx = cls.get()
        if not ctx:
            return

        error_type = type(error).__name__
        context = getattr(error, "code", None)

        if ctx.metadata:
            ctx.metadata.error_type = error_type
            if context:
                ctx.metadata.context = context
        else:
            ctx.metadata = BaseAuditMetadata(
                error_type=error_type,
                context=context,
            )