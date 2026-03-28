import functools
import inspect
from os import error

from catchup.audit.contexts import AuditContext
from catchup.audit.enums import AuditEventStatus
from catchup.audit.enums import AuditLevel
from catchup.audit.metadata import BaseAuditMetadata
from catchup.audit.service import emit_audit_event
from catchup.events.enums import BaseEventAction
from catchup.events.enums import EventType


def audit_log(
    event_type: EventType,
    event_action: BaseEventAction | None = None,
    level: AuditLevel = AuditLevel.INFO,
):
    """
    서비스 로직을 래핑하여 감사 로그를 발행하는 데코레이터.
    함수 종료 시점에 emit_audit_event() 호출을 강제하고 싶은 경우에 사용한다.

    Args:
        event_type: 데코레이터 선언 시 반드시 주입해야 한다.
        event_action: Optional. 생략하는 경우 반드시 AuditContext.action에 런타임 주입해야 한다.
        level: 생략하는 경우 AuditLevel.INFO로 결정된다.

    Examples:
        [event_action 주입 방식]
        
        아래 방법 중 반드시 하나만 사용해야 한다 (XOR).

        Case 1. 데코레이터에 직접 주입

            Action이 함수 정의 시점에 확정되는 경우에 사용한다.
            단순 조회나 상태 변경 여부와 무관하게 Action이 고정되는 경우에 한하며,
            상태 변경이 수반되어 변경 대상 정보가 필요한 경우에는 사용할 수 없다.

                @audit_log(
                    event_type=EventType.SomeEvent,
                    event_action=SomeEventAction.READ,
                )
                def get_something(...):
                    ...

        Case 2. AuditContext.action에 런타임 주입

            Action이 런타임 상태에 의존하여 결정되는 경우에 사용한다.
            이 경우, 반드시 비즈니스 로직 실행 전(예외 발생 가능 지점 이전)에
            AuditContext.action을 결정해야 한다.
            _emit() 호출 시점에 데코레이터의 event_action과 AuditContext.action 중
            정확히 하나만 존재함을 보장해야 하기 때문이다.

                @audit_log(
                    event_type=EventType.SomeEvent
                )
                async def update_something(...):
                    AuditContext.get().action = resolve_action(...)
                    ...
            
        [metadata 전파 방법]
        
        서비스 로직 실행 중 감사 로그에 포함해야 하는 메타데이터는
        AuditContext를 통해 데코레이터로 전파할 수 있다.
        이를 위해 각 도메인마다 audit/metadata.py에 
        BaseAuditMetadata를 상속한 커스텀 pydantic 스키마를 정의해야 한다.
        
            @audit_log(
                event_type=EventType.SomeEvent
            )
            async def update_something(...):
                ...
                val1 = meta1
                val2 = meta2
                ...
                AuditContext.get().metadata = DomainAuditMetadata(
                    attr1=val1,
                    attr2=val2,
                )
                ...

        [주의사항]
        - event_action과 AuditContext.action이 둘 다 없거나, 둘 다 있으면 AssertionError가 발생한다.
        - AuditContext.action 주입이 예외 발생 이후로 미뤄지면 FAIL 시점에 action이 없어
          AssertionError가 발생한다.
        - 하나의 함수에서 여러 Action을 emit해야 하는 경우에는 emit_audit_event()를 직접 호출한다.
        - 다음과 같은 경우에는 데코레이터 대신 emit_audit_event() 직접 호출을 고려해야 한다.

          1. DB 조회 이후에 Action이 결정되는 경우
             DB 조회에 실패하는 경우 BaseEventAction이 정의되지 않아
             _emit()에서 AssertionError가 발생한다.

          2. asyncio.create_task()나 BackgroundTasks.add_task()로 분기된 경우
             _emit() 호출 시점은 래핑된 함수가 종료하는 시점이므로
             실제 I/O 작업 완료 시각과 일치하지 않는 근본적인 한계가 있다.

          3. asyncio.to_thread()나 fastapi.concurrency.run_in_threadpool()을 사용하는 경우
             새로운 스레드 풀에는 AuditContext가 복사되어 전달되므로, 별도 스레드에서
             저장한 컨텍스트는 메인 스레드의 컨텍스트에 반영되지 않는다.
             만약 별도 스레드 풀에 작업을 던지기 전에 AuditContext.action을
             결정할 수 있다면 데코레이터 + AuditContext 조합(Case 2)이 가능하다.
    """
    
    def _emit(
        status: AuditEventStatus,
        level: AuditLevel,
        error_type: str | None = None,
    ):
        ctx = AuditContext.get()
        
        ctx_metadata = ctx.metadata if ctx else None
        ctx_action = ctx.action if ctx else None
        
        assert not(
            event_action is None and ctx_action is None
        ), "BaseEventAction은 데코레이터나 AuditContext.action에 반드시 주입되어야 합니다."
        
        assert not(
            event_action and ctx_action
        ), "BaseEventAction은 데코레이터나 AuditContext.action 중 하나에만 주입되어야 합니다."

        if error_type:
            if ctx_metadata:
                ctx_metadata.error_type = error_type
            else:
                ctx_metadata = BaseAuditMetadata(error_type=error_type)
        
        action = event_action if event_action else ctx_action
        
        emit_audit_event(
            event_type=event_type,
            event_action=action,
            event_status=status,
            level=level,
            metadata=ctx_metadata,
        )
        
    def decorator(func):
        # 래핑 대상 함수가 async def인 경우
        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                try:
                    result = await func(*args, **kwargs)
                    
                    # SUCCESS
                    _emit(
                        status=AuditEventStatus.SUCCESS,
                        level=level
                    )
                    return result
                except Exception as e:
                    # FAIL
                    _emit(
                        status=AuditEventStatus.FAIL, 
                        level=AuditLevel.ERROR,
                        error_type=type(e).__name__
                    )
                    raise
        # 래핑 대상 함수가 def (sync)인 경우
        else:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                try:
                    result = func(*args, **kwargs)
                    
                    # SUCCESS
                    _emit(
                        status=AuditEventStatus.SUCCESS,
                        level=level
                    )
                    return result
                except Exception as e:
                    # FAIL
                    _emit(
                        status=AuditEventStatus.FAIL, 
                        level=AuditLevel.ERROR,
                        error_type=type(e).__name__
                    )
                    raise
                
        return wrapper

    return decorator
