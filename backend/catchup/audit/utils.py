from dataclasses import dataclass
import functools
import inspect
from typing import Any
from typing import Callable

from catchup.audit.base import AuditLevel
from catchup.audit.base import AuditStatus
from catchup.audit.base import BaseAuditAction
from catchup.audit.base import BaseAuditMetadata
from catchup.audit.contexts import AuditContext
from catchup.audit.emitters import emit_audit_event


@dataclass(slots=True, frozen=True)
class AuditLogMetadataInput:
    func: Callable[..., Any]
    arguments: dict[str, Any]
    status: AuditStatus
    action: BaseAuditAction | None
    result: Any = None
    exception: Exception | None = None


AuditMetadataFactory = Callable[[AuditLogMetadataInput], BaseAuditMetadata | None]


def audit_log(
    action: BaseAuditAction | None = None,
    level: AuditLevel = AuditLevel.INFO,
    metadata_factory: AuditMetadataFactory | None = None,
    emit_attempt: bool = False,
):
    """
    서비스 로직을 래핑하여 감사 로그를 발행하는 데코레이터.
    함수 종료 시점에 emit_audit_event() 호출을 강제하고 싶은 경우에 사용한다.

    Args:
        action: 데코레이터 선언 시 주입하거나, 생략하는 경우 반드시 AuditContext.action에 런타임 주입해야 한다.
        level: 생략하는 경우 AuditLevel.INFO로 결정된다.

    Examples:
        [action 주입 방식]

        아래 방법 중 반드시 하나만 사용해야 한다 (XOR).

        Case 1. 데코레이터에 직접 주입

            Action이 함수 정의 시점에 확정되는 경우에 사용한다.
            단순 조회나 상태 변경 여부와 무관하게 Action이 고정되는 경우에 한하며,
            상태 변경이 수반되어 변경 대상 정보가 필요한 경우에는 사용할 수 없다.

                @audit_log(SomeAction.READ)
                def get_something(...):
                    ...

        Case 2. AuditContext.action에 런타임 주입

            Action이 런타임 상태에 의존하여 결정되는 경우에 사용한다.
            이 경우, 반드시 비즈니스 로직 실행 전(예외 발생 가능 지점 이전)에
            AuditContext.action을 결정해야 한다.
            _emit() 호출 시점에 데코레이터의 action과 AuditContext.action 중
            정확히 하나만 존재함을 보장해야 하기 때문이다.

                @audit_log()
                async def update_something(...):
                    AuditContext.get().action = resolve_action(...)
                    ...

        [metadata 전파 방법]

        metadata_factory를 지정한 경우에는
        래핑 대상 함수의 인자/반환값/예외를 기반으로 metadata를 자동 조립

                @audit_log(
                    SomeAction.UPDATE,
                    metadata_factory=DomainAuditMetadata.from_audit,
                )
                async def update_something(...):
                    ...

        metadata_factory를 지정하지 않은 경우에는
        기존처럼 AuditContext를 통해 metadata를 수동으로 추가함

                @audit_log(SomeAction.UPDATE)
                async def update_something(...):
                    AuditContext.get().metadata = DomainAuditMetadata(
                        attr1=val1,
                        attr2=val2,
                    )
                    ...

        [주의사항]
        - action과 AuditContext.action이 둘 다 없거나, 둘 다 있으면 AssertionError가 발생한다.
        - AuditContext.action 주입이 예외 발생 이후로 미뤄지면 FAILURE 시점에 action이 없어
          AssertionError가 발생한다.
        - metadata_factory를 지정한 경우에는 AuditContext.metadata를 읽지 않는다.
        - metadata_factory를 지정하지 않은 경우에만 AuditContext.metadata 수동 주입을 사용한다.
        - metadata.context는 예외 객체의 code 속성이 있을 때만 채워진다.
        - 하나의 함수에서 여러 Action을 emit해야 하는 경우에는 emit_audit_event()를 직접 호출한다.
        - 다음과 같은 경우에는 데코레이터 대신 emit_audit_event() 직접 호출을 고려해야 한다.

          1. DB 조회 이후에 Action이 결정되는 경우
             DB 조회에 실패하는 경우 action이 정의되지 않아
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

    def _resolve_action() -> BaseAuditAction:
        ctx = AuditContext.get()
        ctx_action = ctx.action if ctx else None

        assert not (
            action is None and ctx_action is None
        ), "BaseAuditAction은 데코레이터나 AuditContext.action에 반드시 주입되어야 합니다."

        assert not (
            action and ctx_action
        ), "BaseAuditAction은 데코레이터나 AuditContext.action 중 하나에만 주입되어야 합니다."

        return action or ctx_action

    def _bind_arguments(
        func: Callable[..., Any],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        bound = inspect.signature(func).bind_partial(*args, **kwargs)
        bound.apply_defaults()
        return dict(bound.arguments)

    def _resolve_metadata(
        *,
        func: Callable[..., Any],
        arguments: dict[str, Any],
        status: AuditStatus,
        resolved_action: BaseAuditAction,
        result: Any = None,
        exception: Exception | None = None,
    ) -> BaseAuditMetadata | None:
        # 1. metadata_factory가 없으면 기존 수동 경로를 유지한다.
        if metadata_factory is None:
            ctx = AuditContext.get()
            return ctx.metadata if ctx else None

        # 2. metadata_factory가 있으면 AuditContext.metadata를 전혀 보지 않고, AuditLogMetadataInput으로만 Metadata를 조립함
        metadata = metadata_factory(
            AuditLogMetadataInput(
                func=func,
                arguments=arguments,
                status=status,
                action=resolved_action,
                result=result,
                exception=exception,
            )
        )

        assert metadata is None or isinstance(
            metadata, BaseAuditMetadata
        ), "metadata_factory는 BaseAuditMetadata 또는 None을 반환해야 합니다."

        # 3. 예외에 code가 있으면 그것을 metadata.context로 기록한다.
        error_code = getattr(exception, "code", None)
        if error_code is None:
            return metadata

        if metadata is None:
            return BaseAuditMetadata(context=error_code)

        metadata.context = error_code
        return metadata

    def _emit(
        *,
        func: Callable[..., Any],
        arguments: dict[str, Any],
        status: AuditStatus,
        level: AuditLevel,
        result: Any = None,
        exception: Exception | None = None,
    ) -> None:
        resolved_action = _resolve_action()
        metadata = _resolve_metadata(
            func=func,
            arguments=arguments,
            status=status,
            resolved_action=resolved_action,
            result=result,
            exception=exception,
        )

        emit_audit_event(
            action=resolved_action,
            status=status,
            level=level,
            metadata=metadata,
        )

    def decorator(func: Callable[..., Any]):
        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                arguments = _bind_arguments(func, args, kwargs)

                if emit_attempt:
                    _emit(
                        func=func,
                        arguments=arguments,
                        status=AuditStatus.ATTEMPT,
                        level=level,
                    )

                try:
                    result = await func(*args, **kwargs)
                    _emit(
                        func=func,
                        arguments=arguments,
                        status=AuditStatus.SUCCESS,
                        level=level,
                        result=result,
                    )
                    return result
                except Exception as exc:
                    if metadata_factory is None:
                        error_code = getattr(exc, "code", None)
                        if error_code:
                            AuditContext.set_context(error_code)

                    _emit(
                        func=func,
                        arguments=arguments,
                        status=AuditStatus.FAILURE,
                        level=AuditLevel.WARNING,
                        exception=exc,
                    )
                    raise

        else:

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                arguments = _bind_arguments(func, args, kwargs)

                if emit_attempt:
                    _emit(
                        func=func,
                        arguments=arguments,
                        status=AuditStatus.ATTEMPT,
                        level=level,
                    )

                try:
                    result = func(*args, **kwargs)
                    _emit(
                        func=func,
                        arguments=arguments,
                        status=AuditStatus.SUCCESS,
                        level=level,
                        result=result,
                    )
                    return result
                except Exception as exc:
                    if metadata_factory is None:
                        error_code = getattr(exc, "code", None)
                        if error_code:
                            AuditContext.set_context(error_code)

                    _emit(
                        func=func,
                        arguments=arguments,
                        status=AuditStatus.FAILURE,
                        level=AuditLevel.WARNING,
                        exception=exc,
                    )
                    raise

        return wrapper

    return decorator