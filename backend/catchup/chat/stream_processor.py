from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field
from typing import Any

import structlog

from catchup.audit.actions import ChatAction
from catchup.audit.base import AuditLevel
from catchup.audit.base import AuditStatus
from catchup.audit.emitters import emit_audit_event
from catchup.audit.metadata import ChatAuditMetadata
from catchup.chat.schemas import NODE_STATUS_MAP
from catchup.chat.schemas import ChatStreamingSourceResponse
from catchup.chat.schemas import ChatStreamingStatusResponse
from catchup.chat.schemas import ChatStreamingProcessResponse
from catchup.chat.schemas import ChatStreamingTokenResponse
from catchup.chat.schemas import StreamEvent
from catchup.costs.contexts.chat import ChatTokenUsageContext
from catchup.rag.schemas.sources import BaseSource
from catchup.rag.static_reasoning import STATIC_REASONING_NODES
from catchup.rag.static_reasoning import get_static_reasoning

logger = structlog.get_logger()


@dataclass
class StreamContext:
    """SSE 스트리밍 중 유지되는 상태."""

    langfuse_trace_id: str | None = None
    buffer: str = field(default="")
    is_citation_reached: bool = False
    has_streamed: bool = False
    current_node: str | None = None


class ChatStreamProcessor:
    """
    LangGraph astream_events 이벤트를 SSE StreamEvent로 변환한다.
    """

    def __init__(
        self,
        session_id: uuid.UUID,
        room_id: int,
        save_message: Callable[..., Any],
        langfuse_trace_id: str | None = None,
    ):
        self.session_id = session_id
        self.room_id = room_id
        self._save_message = save_message
        self.context = StreamContext(langfuse_trace_id=langfuse_trace_id)

    async def process(
        self,
        event: dict[str, Any],
    ) -> AsyncGenerator[StreamEvent, None]:
        """단일 LangGraph 이벤트를 파싱해 0개 이상의 StreamEvent를 yield한다."""
        kind = event["event"]
        name = event["name"]

        # 현재 실행 중인 LangGraph 노드 추적
        if kind == "on_chain_start":
            lg_node = event.get("metadata", {}).get("langgraph_node")
            if lg_node:
                self.context.current_node = lg_node

        # 최종 답변에서 인용구가 발견된 경우 스트리밍 차단.
        # 단, has_citations 노드의 종료 이벤트는 최종 sources 전송을 위해 통과시킨다.
        if self.context.is_citation_reached:
            tags = event.get("metadata", {}).get("tags", []) or []
            if not (kind == "on_chain_end" and "has_citations" in tags):
                return

        # 1. 노드 시작
        if kind == "on_chain_start":
            async for res in self._handle_node_start(event):
                yield res

        # 2. 토큰 스트리밍 처리
        elif kind == "on_chat_model_stream":
            async for res in self._handle_token_stream(event):
                yield res

        # 3. clarify 노드 단어 단위 가짜 스트리밍 (LLM 없이 adispatch_custom_event로 발송)
        elif kind == "on_custom_event" and name == "clarify_token":
            token = event["data"].get("token", "")
            if token:
                self.context.has_streamed = True
                yield ChatStreamingTokenResponse(session_id=self.session_id, token=token)

        # 4. process 스트리밍 (supervisor 등에서 adispatch_custom_event로 발송)
        elif kind == "on_custom_event" and name == "process":
            data = event["data"]
            yield ChatStreamingProcessResponse(
                session_id=self.session_id,
                status=data.get("status"),
                node=data.get("node"),
                reasoning=data.get("reasoning"),
                content=data.get("content"),
            )

        # 5. 노드 종료 (현재는 최종 답변 생성 노드만 관여)
        elif kind == "on_chain_end":
            async for res in self._handle_node_end(event):
                yield res

    async def _handle_node_start(
        self,
        event: dict,
    ) -> AsyncGenerator[StreamEvent, None]:
        """노드 단위 답변 생성 과정 스트리밍"""
        name = event["name"]
        tags = event.get("metadata", {}).get("tags", []) or []

        input_data = event["data"].get("input", {})

        if name in NODE_STATUS_MAP:
            n = len(input_data.get("retrieved_docs", []))
            reasoning = (
                get_static_reasoning(name, n=n)
                if name in STATIC_REASONING_NODES
                else None
            )
            yield ChatStreamingProcessResponse(
                status="in_progress",
                session_id=self.session_id,
                node=name,
                reasoning=reasoning,
            )

        # 답변 생성 노드 시작 시: 초기 출처 후보 목록 전송
        if "has_citations" in tags:
            docs = input_data.get("retrieved_docs", [])
            sources = [
                BaseSource.from_document(index=i, doc=doc)
                for i, doc in enumerate(docs, start=1)
            ]
            emit_audit_event(
                action=ChatAction.PROVIDE_SOURCES,
                status=AuditStatus.SUCCESS,
                level=AuditLevel.INFO,
                metadata=ChatAuditMetadata(
                    session_id=self.session_id,
                    provided_sources_count=len(sources),
                    provided_source_ids=[src.id for src in sources],
                ),
            )

            yield ChatStreamingSourceResponse(session_id=self.session_id, sources=sources)

    async def _handle_token_stream(
        self,
        event: dict,
    ) -> AsyncGenerator[StreamEvent, None]:
        """토큰 스트리밍 (citation 태그 노출 차단 포함)"""
        chunk = event["data"].get("chunk")
        tags = event.get("metadata", {}).get("tags", []) or []

        # stream_target 태그가 없으면 사용자 노출 대상이 아님 (graph.py / subgraphs/*.py 참고).
        # clarify는 LLM 호출이 없으므로 이 분기에 진입하지 않음 (on_custom_event로 처리).
        if not ("stream_target" in tags and chunk and chunk.content):
            return

        # extended_thinking 모델은 chunk.content가 list of blocks
        # ([{"type": "thinking"|"reasoning_content"|"text", ...}]) 형태로 옴.
        # 사용자에게는 text 델타만 노출하고 thinking은 버린다.
        raw = chunk.content
        if isinstance(raw, list):
            token = "".join(
                block.get("text", "")
                for block in raw
                if isinstance(block, dict) and block.get("type") == "text"
            )
        else:
            token = raw

        if not token:
            return

        self.context.has_streamed = True

        # has_citations 노드가 아니면 인용 태그 차단 로직이 불필요하므로 그대로 전송
        if "has_citations" not in tags:
            yield ChatStreamingTokenResponse(session_id=self.session_id, token=token)
            return

        # 사용자에게 출처 인용 정보가 담긴 XML 태그가 노출되지 않도록 검증하기 위한 토큰 버퍼
        current_buffer = self.context.buffer + token
        TARGET_TAG = "<citations>"

        # case 1: <citations 태그 발견 -> 즉시 스트리밍 중단 및 앞부분만 전송
        if "<citations" in current_buffer:
            self.context.is_citation_reached = True
            clean_content = current_buffer.split("<citations")[0]
            if clean_content:
                yield ChatStreamingTokenResponse(session_id=self.session_id, token=clean_content)
            return

        # case 2: '<' 포함 -> 버퍼링 여부 결정
        if "<" in current_buffer:
            last_angle_idx = current_buffer.rfind("<")
            safe_part = current_buffer[:last_angle_idx]
            suspicious_part = current_buffer[last_angle_idx:]

            # 의심되는 부분이 태그의 앞 부분과 일치하는지 여부 확인 "<c", "<cit"
            if TARGET_TAG.startswith(suspicious_part):
                if safe_part:
                    yield ChatStreamingTokenResponse(session_id=self.session_id, token=safe_part)
                # 의심스러운 뒷부분만 버퍼에 남김
                self.context.buffer = suspicious_part
                return

        # case 3: 일반 텍스트 -> 전송 & 버퍼 초기화
        yield ChatStreamingTokenResponse(session_id=self.session_id, token=current_buffer)
        self.context.buffer = ""

    async def _handle_node_end(
        self,
        event: dict,
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        그래프 종료 시점.
        인용 사유를 포함한 최종 소스를 업데이트한다.
        """
        tags = event.get("metadata", {}).get("tags", [])
        is_stream_target = "stream_target" in tags

        if not is_stream_target:
            return

        output = event["data"].get("output")
        if not (output and isinstance(output, dict)):
            return

        messages = output.get("messages", [])
        sources = output.get("sources", [])

        last_msg = messages[-1] if messages else None
        final_content = last_msg.content if last_msg and hasattr(last_msg, "content") else str(last_msg)

        final_sources_data = [
            source.model_dump(mode="json") if hasattr(source, "model_dump") else source
            for source in sources
        ]

        trace_id = self.context.langfuse_trace_id

        if final_content:
            message_id = await self._save_message(
                self.room_id,
                "assistant",
                final_content,
                final_sources_data,
                trace_id,
            )

            token_usage_ctx = ChatTokenUsageContext.get()
            if token_usage_ctx and message_id:
                token_usage_ctx.message_id = message_id

            logger.info(
                "final_contents_saved",
                session_id=str(self.session_id),
            )

        # case 1: Fallback 처리: 모델 자체 스트리밍 없이 종료된 경우 메시지 내용 전송
        if not self.context.has_streamed:
            messages = output.get("messages", [])
            if messages:
                last_msg = messages[-1]
                fallback_content = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
                logger.warning(
                    "fallback_answer_sent",
                    context="no_streaming_event",
                    session_id=str(self.session_id),
                )

                yield ChatStreamingTokenResponse(
                    session_id=self.session_id,
                    token=fallback_content,
                )

        # case 2: 인용 사유를 포함한 최종 소스 전송 (빈 목록도 전송해 프론트엔드 상태 동기화)
        if "sources" in output:
            final_sources = output["sources"]
            logger.info(
                "final_sources_sent",
                session_id=str(self.session_id),
                count=len(final_sources),
            )
            yield ChatStreamingSourceResponse(
                session_id=self.session_id, sources=final_sources
            )
