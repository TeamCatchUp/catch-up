from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import structlog

from catchup.chat.integrations.slack_app_mention import SlackChatAnswerRef
from catchup.chat.schemas import ChatStreamingProcessResponse
from catchup.connectors.slack.client import SlackApiClientWrapper
from catchup.server.connector.slack.feedback_actions import build_action_blocks

logger = structlog.get_logger(__name__)

# 최상단 노출 텍스트
PLAN_TITLE = "Catch Up이 답변을 준비하고 있어요"
PLAN_COMPLETED_TITLE = "Catch Up이 답변을 완성했어요 :)"
PLAN_PLACEHOLDER_TASK_ID = "reasoning-1"
PLAN_PLACEHOLDER_TASK_TITLE = "\u200b"

# section fallback 렌더링 제약조건
MAX_SECTION_TEXT = 2900
# Slack markdown block 누적 렌더링 제약조건
MAX_MARKDOWN_BLOCK_TEXT = 12000

# 최종 응답에 포함시킬 출처 URL 개수
MAX_SOURCE_ITEMS = 10

# 스트리밍 버퍼링 크기
MARKDOWN_FLUSH_SIZE = 120

ANSWER_STREAM_NODES = {"direct_answer", "generate_final_answer", "generate_final_answer_fast"}


def build_markdown_text_chunk(text: str) -> dict[str, str]:
    return {
        "type": "markdown_text",
        "text": text,
    }


def build_plan_title_chunk(title: str) -> dict[str, str]:
    return {
        "type": "plan_update",
        "title": title,
    }


@dataclass(slots=True)
class TaskState:
    title: str
    status: str


class SlackPlanState:
    def __init__(self) -> None:
        self.tasks: dict[str, TaskState] = {}
        self.reasoning_task_count = 0
        self.open_reasoning_task_id: str | None = None
        self.placeholder_task_id: str | None = None
        # UI 노출 관련도 높은 출처
        self.top_sources: list[Any] = []

    def build_initial_chunks(self) -> list[dict[str, Any]]:
        self.placeholder_task_id = PLAN_PLACEHOLDER_TASK_ID
        self.reasoning_task_count = max(self.reasoning_task_count, 1)
        self.tasks[PLAN_PLACEHOLDER_TASK_ID] = TaskState(
            title=PLAN_PLACEHOLDER_TASK_TITLE,
            status="pending",
        )
        return [
            build_plan_title_chunk(PLAN_TITLE),
            self._task_chunk(
                task_id=PLAN_PLACEHOLDER_TASK_ID,
                title=PLAN_PLACEHOLDER_TASK_TITLE,
                status="pending",
            ),
        ]

    def apply_process(
        self,
        process: ChatStreamingProcessResponse,
    ) -> list[dict[str, Any]]:
        """Process reasoning -> Plan timeline.

        Visible task copy intentionally comes only from process.reasoning.
        Node names are handled by SlackPlanResponder only for transport control.
        """
        reasoning = (process.reasoning or "").strip()
        if not reasoning:
            if process.status == "in_progress":
                return self._start_placeholder_task()
            return []

        if process.status == "in_progress":
            return self._start_reasoning_task(reasoning)

        if process.status == "completed":
            return self._complete_reasoning_task(reasoning)

        if process.status == "error":
            return self._error_reasoning_task(reasoning)

        return []

    def apply_sources(self, sources: list[Any]) -> list[dict[str, Any]]:
        """Store source candidates for the final response.

        Reasoning-only Plan mode does not render sources inside Plan tasks.
        """
        self.top_sources = list(sources[:MAX_SOURCE_ITEMS])
        return []

    def transition_to_answer(self) -> list[dict[str, Any]]:
        """Complete any visible reasoning before answer streaming begins."""
        return self.complete_open_reasoning_task()

    def finish(self) -> list[dict[str, Any]]:
        return [
            build_plan_title_chunk(PLAN_COMPLETED_TITLE),
            *self.complete_open_reasoning_task(),
        ]

    def fail(self) -> list[dict[str, Any]]:
        return self.complete_open_reasoning_task()

    def build_final_blocks(
        self,
        *,
        query: str,
        answer: str,
        sources: list[Any],
        include_answer_body: bool,
        answer_ref: SlackChatAnswerRef | None = None,
        requester_slack_user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        del query
        visible_sources = sources or self.top_sources
        # 최종 응답은 "본문 markdown"과 "후속 액션 버튼" 두 덩어리로 조립한다.
        final_markdown = build_final_markdown(
            answer=answer,
            sources=visible_sources,
            include_answer_body=include_answer_body,
        )
        blocks: list[dict[str, Any]] = []
        action_blocks = build_action_blocks(answer_ref)
        if not final_markdown and not action_blocks:
            return []
        if len(final_markdown) <= MAX_MARKDOWN_BLOCK_TEXT:
            if final_markdown:
                blocks.append(build_markdown_block(final_markdown))
        else:
            blocks.extend(
                build_overflow_final_blocks(
                    answer=answer,
                    sources=visible_sources,
                    include_answer_body=include_answer_body,
                )
            )
        requester_block = build_requester_markdown_block(
            requester_slack_user_id=requester_slack_user_id,
            answer_ref=answer_ref,
        )
        if requester_block is not None:
            blocks.append(requester_block)
        blocks.extend(action_blocks)
        return blocks

    def _start_reasoning_task(self, title: str) -> list[dict[str, Any]]:
        placeholder_chunk = self._replace_placeholder_task(title=title, status="in_progress")
        if placeholder_chunk is not None:
            return [placeholder_chunk]

        chunks = self.complete_open_reasoning_task()
        chunks.append(self._new_task_chunk(title=title, status="in_progress"))
        self.open_reasoning_task_id = chunks[-1]["id"]
        return chunks

    def _complete_reasoning_task(self, title: str) -> list[dict[str, Any]]:
        placeholder_chunk = self._replace_placeholder_task(title=title, status="complete")
        if placeholder_chunk is not None:
            return [placeholder_chunk]

        open_task = self._open_reasoning_task()
        if open_task is not None and open_task.title == title:
            return self.complete_open_reasoning_task()

        return [
            *self.complete_open_reasoning_task(),
            self._new_task_chunk(title=title, status="complete"),
        ]

    def _error_reasoning_task(self, title: str) -> list[dict[str, Any]]:
        placeholder_chunk = self._replace_placeholder_task(title=title, status="error")
        if placeholder_chunk is not None:
            return [placeholder_chunk]

        return [
            *self.complete_open_reasoning_task(),
            self._new_task_chunk(title=title, status="error"),
        ]

    def _start_placeholder_task(self) -> list[dict[str, Any]]:
        if self.open_reasoning_task_id is not None:
            open_task = self.tasks.get(self.open_reasoning_task_id)
            if open_task is not None and open_task.title != PLAN_PLACEHOLDER_TASK_TITLE:
                return []

        task_id = self.placeholder_task_id or self.open_reasoning_task_id
        if task_id is None:
            self.reasoning_task_count += 1
            task_id = f"reasoning-{self.reasoning_task_count}"

        task = self.tasks.get(task_id)
        if task is not None and task.title == PLAN_PLACEHOLDER_TASK_TITLE and task.status == "in_progress":
            self.placeholder_task_id = task_id
            self.open_reasoning_task_id = task_id
            return []

        self.placeholder_task_id = task_id
        self.open_reasoning_task_id = task_id
        self.tasks[task_id] = TaskState(
            title=PLAN_PLACEHOLDER_TASK_TITLE,
            status="in_progress",
        )
        return [
            self._task_chunk(
                task_id=task_id,
                title=PLAN_PLACEHOLDER_TASK_TITLE,
                status="in_progress",
            )
        ]

    def _replace_placeholder_task(self, *, title: str, status: str) -> dict[str, Any] | None:
        task_id = self.placeholder_task_id or self.open_reasoning_task_id
        if task_id is None:
            return None

        task = self.tasks.get(task_id)
        if task is None or task.title != PLAN_PLACEHOLDER_TASK_TITLE:
            return None

        self.placeholder_task_id = None
        self.open_reasoning_task_id = task_id if status == "in_progress" else None
        self.tasks[task_id] = TaskState(title=title, status=status)
        return self._task_chunk(task_id=task_id, title=title, status=status)

    def complete_open_reasoning_task(self) -> list[dict[str, Any]]:
        open_task_id = self.open_reasoning_task_id
        if open_task_id is None:
            return []

        task = self.tasks.get(open_task_id)
        self.open_reasoning_task_id = None
        if task is None or task.status == "complete":
            return []

        task.status = "complete"
        return [
            self._task_chunk(
                task_id=open_task_id,
                title=task.title,
                status="complete",
            )
        ]

    def _open_reasoning_task(self) -> TaskState | None:
        if self.open_reasoning_task_id is None:
            return None
        return self.tasks.get(self.open_reasoning_task_id)

    def _new_task_chunk(self, *, title: str, status: str) -> dict[str, Any]:
        if self.placeholder_task_id is not None:
            task_id = self.placeholder_task_id
            self.placeholder_task_id = None
        else:
            self.reasoning_task_count += 1
            task_id = f"reasoning-{self.reasoning_task_count}"
        self.tasks[task_id] = TaskState(title=title, status=status)
        return self._task_chunk(task_id=task_id, title=title, status=status)

    def _task_chunk(
        self,
        task_id: str,
        *,
        title: str,
        status: str,
    ) -> dict[str, Any]:
        return {
            "type": "task_update",
            "id": task_id,
            "title": title,
            "status": status,
        }


class SlackPlanResponder:
    def __init__(
        self,
        *,
        client: SlackApiClientWrapper,
        channel_id: str,
        thread_ts: str,
        team_id: str,
        user_id: str,
        query: str,
        plan_stream_ts: str | None,
    ) -> None:
        self.client = client
        self.channel_id = channel_id
        self.thread_ts = thread_ts
        self.team_id = team_id
        self.user_id = user_id
        self.query = query
        self.plan_stream_ts = plan_stream_ts
        self.answer_stream_ts: str | None = None
        self.answer_mode = False
        self.markdown_buffer = ""
        self.has_streamed_answer = False
        self.state = SlackPlanState()

    @classmethod
    async def start(
        cls,
        *,
        client: SlackApiClientWrapper,
        channel_id: str,
        thread_ts: str,
        team_id: str,
        user_id: str,
        query: str,
    ) -> "SlackPlanResponder":
        state = SlackPlanState()
        plan_stream_ts: str | None = None

        try:
            response = await client.start_stream(
                channel=channel_id,
                thread_ts=thread_ts,
                recipient_user_id=user_id,
                recipient_team_id=team_id,
                task_display_mode="plan",
                chunks=state.build_initial_chunks(),
            )
            plan_stream_ts = str(response.get("ts") or "").strip() or None
        except Exception:
            logger.exception(
                "slack_stream_start_failed",
                channel_id=channel_id,
                thread_ts=thread_ts,
                team_id=team_id,
            )

        responder = cls(
            client=client,
            channel_id=channel_id,
            thread_ts=thread_ts,
            team_id=team_id,
            user_id=user_id,
            query=query,
            plan_stream_ts=plan_stream_ts,
        )
        responder.state = state
        return responder

    async def on_process(self, process: ChatStreamingProcessResponse) -> None:
        chunks = self.state.apply_process(process)
        if process.node in ANSWER_STREAM_NODES:
            chunks.extend(self.state.transition_to_answer())
            await self._switch_to_answer_mode(chunks)
            return

        await self._append_plan_chunks(chunks)

    async def on_sources(self, sources: list[Any]) -> None:
        await self._append_plan_chunks(self.state.apply_sources(sources))

    async def append_answer_markdown(self, text: str) -> None:
        if not self.answer_mode or not text:
            return

        self.markdown_buffer += text
        if len(self.markdown_buffer) < MARKDOWN_FLUSH_SIZE and not text.endswith(("\n", ".", "!", "?")):
            return

        await self.flush_answer_markdown()

    async def flush_answer_markdown(self) -> None:
        if not self.answer_mode or not self.markdown_buffer:
            return

        markdown_text = self.markdown_buffer
        self.markdown_buffer = ""
        markdown_chunks = [build_markdown_text_chunk(markdown_text)]

        if self.answer_stream_ts is None:
            # 기본적으로 plan_steam_ts을 그대로 사용하지만, plan block kit 생성에 실패한 경우에만 Fallback으로 답변 생성용 메세지를 새롭게 생성
            response = await self.client.start_stream(
                channel=self.channel_id,
                thread_ts=self.thread_ts,
                recipient_user_id=self.user_id,
                recipient_team_id=self.team_id,
                chunks=markdown_chunks,
            )
            self.answer_stream_ts = str(response.get("ts") or "").strip() or None
            self.has_streamed_answer = True
            return

        await self.client.append_stream(
            channel=self.channel_id,
            ts=self.answer_stream_ts,
            chunks=markdown_chunks,
        )
        self.has_streamed_answer = True

    async def finish(
        self,
        *,
        answer: str,
        sources: list[Any],
        answer_ref: SlackChatAnswerRef | None = None,
    ) -> None:
        # answer_mode 여부에 따라 같은 ts를 종료할지, plan-only ts를 종료할지 갈린다.
        if self.answer_mode:
            await self.flush_answer_markdown()
            await self._finish_answer_stream(
                answer=answer,
                sources=sources,
                answer_ref=answer_ref,
            )
            return

        await self._finish_plan_stream(
            answer=answer,
            sources=sources,
            answer_ref=answer_ref,
        )

    async def fail(self, message: str) -> None:
        if self.answer_mode:
            await self.flush_answer_markdown()
            if self.answer_stream_ts is not None:
                failure_chunks = [build_markdown_text_chunk(message), *self.state.fail()]
                # plan UI를 남긴 채 같은 stream에서 answer task를 error로 종료
                await self.client.stop_stream(
                    channel=self.channel_id,
                    ts=self.answer_stream_ts,
                    chunks=failure_chunks,
                )
                return

            await self.client.post_message(
                channel=self.channel_id,
                thread_ts=self.thread_ts,
                text=message,
            )
            return

        if self.plan_stream_ts is None:
            await self.client.post_message(
                channel=self.channel_id,
                thread_ts=self.thread_ts,
                text=message,
            )
            return

        await self.client.stop_stream(
            channel=self.channel_id,
            ts=self.plan_stream_ts,
            chunks=[build_markdown_text_chunk(message), *self.state.fail()],
            blocks=[],
        )

    async def _switch_to_answer_mode(self, prelude_chunks: list[dict[str, Any]]) -> None:
        if self.answer_mode:
            return

        await self._append_plan_chunks(prelude_chunks)
        if self.answer_stream_ts is None and self.plan_stream_ts is not None:
            # generate_final_answer에서 plan stream을 삭제하지 않고, 같은 ts를 answer streaming 대상으로 재사용
            self.answer_stream_ts = self.plan_stream_ts
        self.answer_mode = True

    async def _finish_answer_stream(
        self,
        *,
        answer: str,
        sources: list[Any],
        answer_ref: SlackChatAnswerRef | None = None,
    ) -> None:
        visible_sources = self.state.top_sources or sources
        blocks = self.state.build_final_blocks(
            query=self.query,
            answer=answer,
            sources=sources,
            include_answer_body=not self.has_streamed_answer,
            answer_ref=answer_ref,
            requester_slack_user_id=self.user_id,
        )

        if self.answer_stream_ts is None:
            await self.client.post_message(
                channel=self.channel_id,
                thread_ts=self.thread_ts,
                text=build_plain_fallback_text(answer=answer, sources=visible_sources),
                blocks=blocks,
            )
            return

        await self.client.stop_stream(
            channel=self.channel_id,
            ts=self.answer_stream_ts,
            chunks=self.state.finish(),
            blocks=blocks,
        )

    async def _finish_plan_stream(
        self,
        *,
        answer: str,
        sources: list[Any],
        answer_ref: SlackChatAnswerRef | None = None,
    ) -> None:
        visible_sources = self.state.top_sources or sources
        blocks = self.state.build_final_blocks(
            query=self.query,
            answer=answer,
            sources=sources,
            include_answer_body=True,
            answer_ref=answer_ref,
            requester_slack_user_id=self.user_id,
        )

        if self.plan_stream_ts is None:
            await self.client.post_message(
                channel=self.channel_id,
                thread_ts=self.thread_ts,
                text=build_plain_fallback_text(answer=answer, sources=visible_sources),
                blocks=blocks,
            )
            return

        await self.client.stop_stream(
            channel=self.channel_id,
            ts=self.plan_stream_ts,
            chunks=self.state.finish(),
            blocks=blocks,
        )

    async def _append_plan_chunks(self, chunks: list[dict[str, Any]]) -> None:
        if self.plan_stream_ts is None or not chunks:
            return

        await self.client.append_stream(
            channel=self.channel_id,
            ts=self.plan_stream_ts,
            chunks=chunks,
        )


def build_plain_fallback_text(
    *,
    answer: str,
    sources: list[Any],
) -> str:
    source_text = build_source_list_markdown(sources)
    if not source_text:
        return answer
    if not answer:
        return source_text
    return f"{answer}\n\n{source_text}"


def build_markdown_block(text: str) -> dict[str, str]:
    return {
        "type": "markdown",
        "text": text,
    }


def build_requester_markdown_block(
    *,
    requester_slack_user_id: str | None,
    answer_ref: SlackChatAnswerRef | None,
) -> dict[str, str] | None:
    if not requester_slack_user_id or answer_ref is None or answer_ref.assistant_message_id is None:
        return None

    return build_markdown_block(f"> 답변 요청자 <@{requester_slack_user_id}>")


def build_section_block(text: str, *, block_id: str) -> dict[str, Any]:
    return {
        "type": "section",
        "block_id": block_id,
        "expand": True,
        "text": {
            "type": "mrkdwn",
            "text": text,
        },
    }


def build_final_markdown(
    *,
    answer: str,
    sources: list[Any],
    include_answer_body: bool,
) -> str:
    # streamed 경로는 sources만, fallback 경로는 answer + sources를 한 markdown으로 만든다.
    parts: list[str] = []
    answer_text = (answer or "").strip()
    source_text = build_source_list_markdown(sources)

    if include_answer_body and answer_text:
        parts.append(answer_text)
    if source_text:
        if parts:
            parts.append("---")
        parts.append(source_text)
    return "\n\n".join(parts).strip()


def build_overflow_final_blocks(
    *,
    answer: str,
    sources: list[Any],
    include_answer_body: bool,
) -> list[dict[str, Any]]:
    # markdown block 한도를 넘는 경우에만 section block으로 안전하게 분리한다.
    blocks: list[dict[str, Any]] = []
    answer_text = (answer or "").strip()
    source_text = build_source_list_markdown(sources)

    if include_answer_body and answer_text:
        for index, section_text in enumerate(split_sections(answer_text), start=1):
            blocks.append(
                build_section_block(
                    section_text,
                    block_id=f"catchup_answer_body_overflow_v1_{index}",
                )
            )

    if source_text:
        if len(source_text) <= MAX_MARKDOWN_BLOCK_TEXT:
            blocks.append(build_markdown_block(source_text))
        else:
            for index, section_text in enumerate(split_sections(source_text), start=1):
                blocks.append(
                    build_section_block(
                        section_text,
                        block_id=f"catchup_sources_overflow_v1_{index}",
                    )
                )

    return blocks


def build_task_sources(sources: list[Any]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []

    for source in sources[:MAX_SOURCE_ITEMS]:
        url = read_source_field(source, "url")
        title = read_source_field(source, "title") or "Source"
        if not url:
            continue

        items.append(
            {
                "type": "url",
                "url": url,
                "text": trim_text(title, 75),
            }
        )

    return items


def build_source_list_markdown(sources: list[Any]) -> str:
    items = build_source_list_items(sources)
    if not items:
        return ""

    return "## Sources\n\n" + "\n\n".join(items)


def build_source_list_items(sources: list[Any]) -> list[str]:
    items: list[str] = []

    for index, source in enumerate(filter_cited_sources(sources), start=1):
        tool = format_source_tool(source)
        link = format_source_link(source)
        updated = format_source_timestamp(source)
        items.append(
            f"{index}. {link}\n{tool} · {updated}"
        )

    return items


def filter_cited_sources(sources: list[Any]) -> list[Any]:
    cited_sources = [
        source
        for source in sources[:MAX_SOURCE_ITEMS]
        if read_source_bool(source, "is_cited")
    ]
    if cited_sources:
        return cited_sources
    return list(sources[:MAX_SOURCE_ITEMS])


def format_source_tool(source: Any) -> str:
    source_name = (read_source_field(source, "source") or "").strip().lower()
    return {
        "slack": "Slack",
        "jira": "Jira",
        "github": "GitHub",
        "confluence": "Confluence",
    }.get(source_name, "Source")


def format_source_link(source: Any) -> str:
    title = trim_text(read_source_field(source, "title") or "Source", 75)
    url = read_source_field(source, "url")
    if not url:
        return title
    return f"[{escape_markdown_link_label(title)}]({url})"


def format_source_timestamp(source: Any) -> str:
    value = (
        read_source_field(source, "updated_at")
        or read_source_field(source, "created_at")
        or ""
    ).strip()
    if not value:
        return "-"
    if "T" in value and len(value) >= 10:
        return value[:10]
    return value


def escape_markdown_link_label(text: str) -> str:
    value = (text or "").strip()
    if not value:
        return "Source"
    return (
        value.replace("[", "\\[")
        .replace("]", "\\]")
        .replace("(", "\\(")
        .replace(")", "\\)")
    )


def read_source_bool(source: Any, field: str) -> bool:
    if hasattr(source, field):
        return bool(getattr(source, field))

    if isinstance(source, dict):
        return bool(source.get(field))

    return False


def read_source_field(source: Any, field: str) -> str | None:
    if hasattr(source, field):
        value = getattr(source, field)
        return str(value) if value else None

    if isinstance(source, dict):
        value = source.get(field)
        if value is None and field == "title":
            value = source.get("text")
        return str(value) if value else None

    return None


def split_sections(text: str) -> list[str]:
    normalized = (text or "").strip()
    if not normalized:
        return [""]

    sections: list[str] = []
    remaining = normalized

    while remaining:
        if len(remaining) <= MAX_SECTION_TEXT:
            sections.append(remaining)
            break

        cut = remaining.rfind("\n", 0, MAX_SECTION_TEXT)
        if cut <= 0:
            cut = MAX_SECTION_TEXT

        sections.append(remaining[:cut].rstrip())
        remaining = remaining[cut:].lstrip()

    return sections


def trim_text(text: str, limit: int) -> str:
    value = re.sub(r"\s+", " ", text or "").strip()
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."
