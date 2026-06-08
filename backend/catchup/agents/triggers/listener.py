from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from typing import Any

import structlog
from redis.exceptions import ResponseError
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.orm import Session

from catchup.agents.factory import get_execution_service
from catchup.agents.schemas import AgentSpec as AgentSpecSchema
from catchup.agents.tools.registry import ToolRegistry
from catchup.agents.triggers.channel_talk_context import (
    CHANNEL_TALK_USER_CHAT_CONTEXT_KEY,
)
from catchup.agents.triggers.channel_talk_context import CHANNEL_TALK_USER_CHAT_ID_KEY
from catchup.agents.triggers.channel_talk_context import (
    build_channel_talk_user_chat_inputs,
)
from catchup.agents.triggers.events import AgentWebhookEvent
from catchup.agents.triggers.stream import AGENT_RUN_REQUEST_CLAIM_START_ID
from catchup.agents.triggers.stream import AGENT_RUN_REQUEST_CONSUMER_GROUP
from catchup.agents.triggers.stream import AGENT_RUN_REQUEST_READ_NEW_MESSAGE_ID
from catchup.agents.triggers.stream import AGENT_RUN_REQUEST_STREAM_KEY
from catchup.agents.triggers.stream import AckDeleteResult
from catchup.agents.triggers.stream import AgentRunRequest
from catchup.agents.triggers.stream import AgentRunStreamMessage
from catchup.agents.triggers.stream import decode_agent_run_stream_entries
from catchup.automations.runner import AutomationInput
from catchup.automations.runner import run_inquiry_automation
from catchup.db.agent_specs import build_agent_global_context
from catchup.db.engine import SessionLocal
from catchup.db.models import AgentSpec
from catchup.db.models import AgentStatus
from catchup.db.models import AgentTrigger
from catchup.db.models import AgentTriggerOutbox
from catchup.db.models import AgentTriggerOutboxStatus
from catchup.db.models import AgentTriggerRun
from catchup.db.models import AgentTriggerRunStatus
from catchup.utils.redis import get_redis_client
from catchup.utils.redis import get_stream_redis_client

logger = structlog.get_logger(__name__)


@dataclass(slots=True, frozen=True)
class AgentRunProcessResult:
    """Stream 메시지를 ACK할지와 실제 실행 context를 함께 전달한다."""

    should_ack: bool
    execution: AgentRunExecutionContext | None = None


@dataclass(slots=True, frozen=True)
class AgentRunExecutionContext:
    """DB claim 이후 비동기 ExecutionService 호출에 필요한 불변 context."""

    run_id: int
    message_id: str
    spec_id: int
    spec: AgentSpecSchema
    user_input_values: dict[str, Any]
    event: AgentWebhookEvent
    global_context: Any


async def ensure_agent_run_consumer_group() -> None:
    """worker 재시작이 기존 Redis consumer group을 깨지 않게 보장한다."""
    redis = await get_redis_client()
    try:
        await redis.xgroup_create(
            name=AGENT_RUN_REQUEST_STREAM_KEY,
            groupname=AGENT_RUN_REQUEST_CONSUMER_GROUP,
            id=AGENT_RUN_REQUEST_CLAIM_START_ID,
            mkstream=True,
        )
    except ResponseError as exc:
        if "BUSYGROUP" in str(exc):
            return
        raise


async def read_agent_run_messages(
    *,
    consumer_name: str,
    count: int = 10,
    block_ms: int = 0,
) -> list[AgentRunStreamMessage]:
    """새 run request 메시지를 consumer group에서 읽는다."""
    redis = await get_stream_redis_client()
    kwargs: dict[str, Any] = {
        "groupname": AGENT_RUN_REQUEST_CONSUMER_GROUP,
        "consumername": consumer_name,
        "streams": {AGENT_RUN_REQUEST_STREAM_KEY: AGENT_RUN_REQUEST_READ_NEW_MESSAGE_ID},
        "count": max(1, count),
    }
    if block_ms > 0:
        kwargs["block"] = block_ms
    raw = await redis.xreadgroup(**kwargs)
    entries: list[tuple[Any, dict[Any, Any]]] = []
    for _stream, stream_entries in raw:
        entries.extend(stream_entries)
    return decode_agent_run_stream_entries(entries)


async def reclaim_agent_run_messages(
    *,
    consumer_name: str,
    min_idle_ms: int,
    count: int = 10,
) -> list[AgentRunStreamMessage]:
    """처리 중 멈춘 메시지를 같은 DB idempotency 경계로 다시 가져온다."""
    redis = await get_stream_redis_client()
    raw = await redis.xautoclaim(
        name=AGENT_RUN_REQUEST_STREAM_KEY,
        groupname=AGENT_RUN_REQUEST_CONSUMER_GROUP,
        consumername=consumer_name,
        min_idle_time=max(1, min_idle_ms),
        start_id=AGENT_RUN_REQUEST_CLAIM_START_ID,
        count=max(1, count),
    )
    raw_entries = raw[1] if isinstance(raw, (list, tuple)) and len(raw) > 1 else []
    return decode_agent_run_stream_entries(raw_entries)


async def process_agent_run_message(message: AgentRunStreamMessage) -> None:
    """Stream delivery와 실제 agent 실행 사이의 commit 순서를 고정한다.

    DB claim commit이 끝난 뒤에만 ExecutionService.run()을 호출해야 중복
    delivery가 와도 같은 run을 두 worker가 동시에 실행하지 않는다.
    """
    if message.malformed or message.request is None:
        await ack_agent_run_message(message.message_id)
        return
    process_result = await asyncio.to_thread(_prepare_agent_run_message, message)
    should_ack = process_result.should_ack
    if process_result.execution is not None:
        if await asyncio.to_thread(_mark_execution_started, process_result.execution):
            execution_result, execution_error = await _execute_agent_run(
                process_result.execution
            )
            should_ack = await asyncio.to_thread(
                _record_agent_run_terminal_state,
                run_id=process_result.execution.run_id,
                result=execution_result,
                error=execution_error,
            )
        else:
            should_ack = False
    if should_ack:
        await ack_agent_run_message(message.message_id)


def _prepare_agent_run_message(
    message: AgentRunStreamMessage,
) -> AgentRunProcessResult:
    """메시지 claim 단계의 DB 세션을 agent 실행 단계와 분리한다."""
    if message.request is None:
        return AgentRunProcessResult(should_ack=True)
    db = SessionLocal()
    try:
        process_result = run_agent_request(
            db=db,
            request=message.request,
            message_id=message.message_id,
        )
        db.commit()
        return process_result
    except Exception as exc:
        db.rollback()
        logger.exception(
            "agent_trigger_run_message_processing_failed",
            run_id=message.request.run_id,
            message_id=message.message_id,
            error=str(exc),
        )
        return AgentRunProcessResult(should_ack=False)
    finally:
        db.close()


async def run_agent_trigger_listener_forever(
    stop_event: asyncio.Event,
    *,
    consumer_name: str = "agent-trigger-listener",
) -> None:
    """Redis Stream consumer group을 돌며 run request를 at-least-once 처리한다."""
    await ensure_agent_run_consumer_group()
    while not stop_event.is_set():
        messages = await read_agent_run_messages(
            consumer_name=consumer_name,
            count=5,
            block_ms=1000,
        )
        for message in messages:
            await process_agent_run_message(message)
        reclaimed = await reclaim_agent_run_messages(
            consumer_name=consumer_name,
            min_idle_ms=1_800_000,
            count=5,
        )
        for message in reclaimed:
            await process_agent_run_message(message)


def run_agent_request(
    db: Session,
    request: AgentRunRequest,
    *,
    message_id: str,
) -> AgentRunProcessResult:
    """Stream request가 현재 DB run 상태와 일치할 때만 실행 context를 만든다."""
    run = db.get(AgentTriggerRun, request.run_id)
    if run is None:
        return AgentRunProcessResult(should_ack=True)
    if run.status != AgentTriggerRunStatus.DISPATCHING:
        should_ack = run.status in {
            AgentTriggerRunStatus.COMPLETED,
            AgentTriggerRunStatus.FAILED,
            AgentTriggerRunStatus.CANCELLED,
        }
        return AgentRunProcessResult(should_ack=should_ack)
    if not request.dispatch_token or str(run.dispatch_token) != request.dispatch_token:
        return AgentRunProcessResult(should_ack=True)
    trigger = db.get(AgentTrigger, run.trigger_id)
    if trigger is None:
        run.status = AgentTriggerRunStatus.FAILED
        run.last_error = "agent_trigger_missing"
        return AgentRunProcessResult(should_ack=True)
    if not _request_matches_db_state(request=request, run=run, trigger=trigger):
        return AgentRunProcessResult(should_ack=True)
    if not _claim_run_execution(db=db, run_id=run.id, message_id=message_id):
        return AgentRunProcessResult(should_ack=False)

    agent_spec_row = db.get(AgentSpec, trigger.agent_spec_id)
    if agent_spec_row is None or agent_spec_row.status != AgentStatus.ACTIVE:
        run.status = AgentTriggerRunStatus.FAILED
        run.last_error = "agent_spec_inactive_or_missing"
        return AgentRunProcessResult(should_ack=True)

    try:
        event = _event_from_run(run)
        spec = AgentSpecSchema.model_validate(agent_spec_row.spec)
        global_context = build_agent_global_context(
            db=db,
            workspace_id=agent_spec_row.workspace_id,
            user_id=agent_spec_row.user_id,
        )
    except Exception as exc:
        run.status = AgentTriggerRunStatus.FAILED
        run.last_error = str(exc)
        return AgentRunProcessResult(should_ack=True)

    return AgentRunProcessResult(
        should_ack=False,
        execution=AgentRunExecutionContext(
            run_id=run.id,
            message_id=message_id,
            spec_id=agent_spec_row.id,
            spec=spec,
            user_input_values=agent_spec_row.user_input_values or {},
            event=event,
            global_context=global_context,
        ),
    )


async def _execute_agent_run(
    context: AgentRunExecutionContext,
) -> tuple[str | None, str | None]:
    """DB 트랜잭션 밖에서 실제 agent를 실행해 lock 보유 시간을 만들지 않는다."""
    if _is_channeltalk_inquiry_event(context.event):
        try:
            automation_input = await _build_automation_input(context)
            if automation_input is not None:
                await run_inquiry_automation(automation_input)
                return "", None
        except Exception as exc:
            return None, str(exc)
        return "", None

    ToolRegistry.bind_execution_context(
        context.spec.tools,
        references=context.spec.references,
        global_context=context.global_context,
        trigger_event=context.event,
    )
    service = get_execution_service()
    try:
        user_input_values = await _build_execution_user_inputs(context)
        result = await service.run(
            spec_id=context.spec_id,
            spec=context.spec,
            user_input_values=user_input_values,
            trigger_event=context.event,
        )
    except Exception as exc:
        return None, str(exc)
    return result, None


def _is_channeltalk_inquiry_event(event: AgentWebhookEvent) -> bool:
    """이벤트가 ChannelTalk 문의 대응 자동화 대상인지 확인한다."""
    return (
        event.source == "channel_talk"
        and event.event_type in {"user_chat.created", "user_chat.new_message"}
    )


async def _build_automation_input(
    context: AgentRunExecutionContext,
) -> AutomationInput | None:
    """AgentRunExecutionContext에서 AutomationInput을 구성한다."""
    ct_inputs = await build_channel_talk_user_chat_inputs(context.event.payload)
    if not ct_inputs:
        return None

    inquiry_text: str = ct_inputs.get(CHANNEL_TALK_USER_CHAT_CONTEXT_KEY, "")
    user_chat_id: str = ct_inputs.get(CHANNEL_TALK_USER_CHAT_ID_KEY, "")

    slack_channel_id = ""
    slack_credential_id: int | None = None
    for ref_list in (context.spec.references or {}).values():
        for ref in ref_list:
            if ref.kind == "slack_channel" and ref.values:
                config = next(iter(ref.values.values()))
                slack_channel_id = str(config.get("channel_id") or "").strip()
                cred = config.get("credential_id")
                if cred is not None:
                    slack_credential_id = int(cred)
                break
        if slack_channel_id:
            break

    if not slack_channel_id or slack_credential_id is None:
        logger.warning(
            "automation_input_missing_slack_config",
            user_chat_id=user_chat_id,
        )
        return None

    return AutomationInput(
        inquiry_text=inquiry_text,
        user_chat_id=user_chat_id,
        slack_channel_id=slack_channel_id,
        slack_credential_id=slack_credential_id,
        global_context=context.global_context,
    )


async def _build_execution_user_inputs(
    context: AgentRunExecutionContext,
) -> dict[str, Any]:

    user_input_values = dict(context.user_input_values)
    if (
        context.event.source == "channel_talk"
        and context.event.event_type in {"user_chat.created", "user_chat.new_message"}
    ):
        user_input_values.update(
            await build_channel_talk_user_chat_inputs(context.event.payload)
        )
    return user_input_values


def _record_agent_run_terminal_state(
    *,
    run_id: int,
    result: str | None,
    error: str | None,
) -> bool:
    """실행 결과를 run ledger에 닫고 ACK 가능 여부를 결정한다."""
    db = SessionLocal()
    try:
        run = db.get(AgentTriggerRun, run_id)
        if run is None:
            db.commit()
            return True
        if run.status != AgentTriggerRunStatus.DISPATCHING:
            should_ack = run.status in {
                AgentTriggerRunStatus.COMPLETED,
                AgentTriggerRunStatus.FAILED,
                AgentTriggerRunStatus.CANCELLED,
            }
            db.commit()
            return should_ack
        if error is not None:
            run.status = AgentTriggerRunStatus.FAILED
            run.last_error = error
        else:
            run.status = AgentTriggerRunStatus.COMPLETED
            run.last_error = None
            run.policy_metadata = {
                **(run.policy_metadata or {}),
                "result": result,
                "finished_at": datetime.now(timezone.utc).isoformat(),
            }
        db.commit()
        return True
    except Exception as exc:
        db.rollback()
        logger.exception(
            "agent_trigger_run_terminal_state_update_failed",
            run_id=run_id,
            error=str(exc),
        )
        return False
    finally:
        db.close()

async def ack_agent_run_message(message_id: str) -> AckDeleteResult:
    """DB terminal state가 확정된 메시지만 ACK와 삭제를 함께 수행한다."""
    redis = await get_redis_client()
    acked = int(
        await redis.xack(
            AGENT_RUN_REQUEST_STREAM_KEY,
            AGENT_RUN_REQUEST_CONSUMER_GROUP,
            message_id,
        )
    )
    deleted = int(await redis.xdel(AGENT_RUN_REQUEST_STREAM_KEY, message_id))
    return AckDeleteResult(acked=acked, deleted=deleted)


def _event_from_run(run: AgentTriggerRun) -> AgentWebhookEvent:
    """worker가 원본 webhook context를 재구성하는 단일 metadata 경계."""
    metadata = run.policy_metadata or {}
    latest_event = metadata.get("latest_event")
    if not isinstance(latest_event, dict):
        raise ValueError("agent trigger run is missing latest_event metadata")
    return AgentWebhookEvent.model_validate(latest_event)


def _claim_run_execution(*, db: Session, run_id: int, message_id: str) -> bool:
    """Stream message와 run을 원자적으로 묶어 중복 worker 실행을 막는다."""
    now = datetime.now(timezone.utc)
    outbox_result = db.execute(
        update(AgentTriggerOutbox)
        .where(
            AgentTriggerOutbox.run_id == run_id,
            or_(
                AgentTriggerOutbox.stream_message_id.is_(None),
                AgentTriggerOutbox.stream_message_id == message_id,
            ),
        )
        .values(
            status=AgentTriggerOutboxStatus.PUBLISHED,
            stream_message_id=message_id,
            updated_at=now,
        )
        .returning(AgentTriggerOutbox.run_id)
    )
    if outbox_result.scalar_one_or_none() is None:
        return False

    run_result = db.execute(
        update(AgentTriggerRun)
        .where(
            AgentTriggerRun.id == run_id,
            AgentTriggerRun.status == AgentTriggerRunStatus.DISPATCHING,
            AgentTriggerRun.execution_started_at.is_(None),
        )
        .values(updated_at=now)
        .returning(AgentTriggerRun.id)
    )
    claimed = run_result.scalar_one_or_none() is not None
    if claimed:
        db.flush()
    return claimed


def _mark_execution_started(context: AgentRunExecutionContext) -> bool:
    """실제 ExecutionService 호출 직전 시각을 별도 세션에서 확정한다."""
    db = SessionLocal()
    now = datetime.now(timezone.utc)
    try:
        outbox_id = db.scalar(
            select(AgentTriggerOutbox.id)
            .where(
                AgentTriggerOutbox.run_id == context.run_id,
                AgentTriggerOutbox.stream_message_id == context.message_id,
            )
            .limit(1)
        )
        if outbox_id is None:
            db.rollback()
            return False

        result = db.execute(
            update(AgentTriggerRun)
            .where(
                AgentTriggerRun.id == context.run_id,
                AgentTriggerRun.status == AgentTriggerRunStatus.DISPATCHING,
                AgentTriggerRun.execution_started_at.is_(None),
            )
            .values(
                execution_started_at=now,
                updated_at=now,
            )
            .returning(AgentTriggerRun.id)
        )
        started = result.scalar_one_or_none() is not None
        db.commit()
        return started
    except Exception as exc:
        db.rollback()
        logger.exception(
            "agent_trigger_run_execution_start_update_failed",
            run_id=context.run_id,
            error=str(exc),
        )
        return False
    finally:
        db.close()


def _request_matches_db_state(
    *,
    request: AgentRunRequest,
    run: AgentTriggerRun,
    trigger: AgentTrigger,
) -> bool:
    """Redis Stream payload가 DB source of truth와 같은 실행을 가리키는지 확인한다."""
    return (
        request.trigger_id == run.trigger_id
        and request.agent_spec_id == trigger.agent_spec_id
        and request.event_id == run.latest_event_id
        and request.policy_kind == run.policy_kind
    )
