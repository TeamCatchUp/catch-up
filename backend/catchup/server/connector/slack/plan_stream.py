from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog

from catchup.connectors.slack.client import SlackApiClientWrapper

logger = structlog.get_logger(__name__)

PLAN_TITLE = "답변을 생성중입니다 ..."
MAX_HEADER_TEXT = 120
MAX_SECTION_TEXT = 2900
MAX_SOURCE_ITEMS = 5
MARKDOWN_FLUSH_SIZE = 120
STREAMING_NODES = {"generate_final_answer"}

TASK_ORDER = ("route", "rewrite", "search", "rerank", "grade", "answer")

TASK_TITLES = {
    "route": "질문의 의도를 파악하고 있습니다",
    "rewrite": "검색을 준비하고 있습니다",
    "search": "사내 지식을 살펴보고 있습니다",
    "rerank": "중요한 문서만 고르고 있습니다",
    "grade": "검색 품질을 점검하고 있어요",
    "answer": "최종 답변을 작성중 ...",
}

TASK_DETAILS = {
    "route": "질문의 의도를 파악하고 있어요.",
    "rewrite": "검색 질의를 준비하고 있어요.",
    "search": "관련 문서를 찾고 있어요.",
    "rerank": "중요한 문서를 추리고 있어요.",
    "grade": "검색 품질을 점검하고 있어요.",
    "answer": "문서를 참고하여 답변을 작성하고 있어요.",
}

TASK_OUTPUTS = {
    "route": "질문 의도 파악을 마쳤습니다.",
    "rewrite": "검색 준비를 마쳤습니다.",
    "search": "후보 문서를 수집했습니다.",
    "rerank": "상위 5건을 골랐습니다.",
    "grade": "답변에 충분한 문서를 확보했습니다.",
    "answer": "최종 답변 생성을 마쳤습니다.",
}

SEARCH_NODES = {
    "search_vector_db",
    "expand_graph_context",
    "fetch_details_after_graph_context_expansion",
    "fallback_cypher_query",
}

NO_VALUE = object()


@dataclass(slots=True)
class TaskState:
    status: str = "pending"
    details_sent: bool = False
    output_sent: bool = False
    sources_sent: bool = False


class SlackPlanState:
    def __init__(self) -> None:
        self.tasks = {task_id: TaskState() for task_id in TASK_ORDER}
        self.top_sources: list[dict[str, str]] = []

    def build_initial_chunks(self) -> list[dict[str, Any]]:
        chunks: list[dict[str, Any]] = [{"type": "plan_update", "title": PLAN_TITLE}]
        chunks.extend(self._task_chunk(task_id, status="pending") for task_id in TASK_ORDER)
        return chunks

    def apply_node(self, node: str) -> list[dict[str, Any]]:
        if node == "route":
            return self._start_task("route")

        if node in {"rewrite", "generate_vector_queries"}:
            return self._move_to("rewrite", complete_task_ids=("route",))

        if node in SEARCH_NODES:
            return self._move_to("search", complete_task_ids=("rewrite",))

        if node == "rerank":
            return self._move_to("rerank", complete_task_ids=("search",))

        if node == "grade":
            return self._move_to("grade", complete_task_ids=("rerank",))

        if node == "chitchat":
            chunks: list[dict[str, Any]] = []
            chunks.extend(self._complete_task("route"))
            chunks.extend(self._complete_task("rewrite", output="검색 단계를 생략했습니다."))
            chunks.extend(self._complete_task("search", output="검색 단계를 생략했습니다."))
            chunks.extend(self._complete_task("rerank", output="재정렬 단계를 생략했습니다."))
            chunks.extend(self._complete_task("grade", output="품질 점검 단계를 생략했습니다."))
            chunks.extend(self._start_task("answer"))
            return chunks

        return []

    def apply_sources(self, sources: list[Any]) -> list[dict[str, Any]]:
        if not sources:
            return []

        self.top_sources = build_task_sources(sources)
        rerank_output = f"상위 {len(self.top_sources)}건을 골랐습니다."

        updates: list[dict[str, Any]] = []
        updates.extend(self._complete_task("search"))
        updates.extend(self._complete_task("rerank", output=rerank_output, sources=self.top_sources))
        return updates

    def transition_to_answer(self) -> list[dict[str, Any]]:
        updates: list[dict[str, Any]] = []
        updates.extend(self._complete_task("search"))
        updates.extend(self._complete_task("rerank", output=f"상위 {len(self.top_sources) or MAX_SOURCE_ITEMS}건을 골랐습니다.", sources=self.top_sources or None))
        updates.extend(self._complete_task("grade"))
        return updates

    def finish(self) -> list[dict[str, Any]]:
        return self._complete_task("answer")

    def fail(self, message: str) -> list[dict[str, Any]]:
        task = self.tasks["answer"]
        task.status = "error"
        chunk = self._task_chunk("answer", status="error", details=message)
        task.details_sent = True
        return [chunk]

    def build_final_blocks(
        self,
        *,
        query: str,
        answer: str,
        sources: list[Any],
        include_answer_body: bool,
    ) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = []

        if include_answer_body:
            blocks.extend(
                [
                    {"type": "divider"},
                    {
                        "type": "header",
                        "block_id": "catchup_answer_header_v1",
                        "text": {
                            "type": "plain_text",
                            "text": trim_text(query, MAX_HEADER_TEXT),
                        },
                    },
                ]
            )

            for index, section_text in enumerate(split_sections(answer), start=1):
                blocks.append(
                    {
                        "type": "section",
                        "block_id": f"catchup_answer_body_v1_{index}",
                        "text": {
                            "type": "mrkdwn",
                            "text": section_text,
                        },
                    }
                )

        source_text = build_source_markdown(sources)
        if source_text:
            if not blocks:
                blocks.append({"type": "divider"})
            blocks.extend(
                [
                    {
                        "type": "section",
                        "block_id": "catchup_sources_header_v1",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*Sources*",
                        },
                    },
                    {
                        "type": "section",
                        "block_id": "catchup_sources_body_v1",
                        "text": {
                            "type": "mrkdwn",
                            "text": source_text,
                        },
                    },
                ]
            )

        return blocks

    def _move_to(
        self,
        task_id: str,
        *,
        complete_task_ids: tuple[str, ...],
    ) -> list[dict[str, Any]]:
        chunks: list[dict[str, Any]] = []
        for complete_task_id in complete_task_ids:
            chunks.extend(self._complete_task(complete_task_id))
        chunks.extend(self._start_task(task_id))
        return chunks

    def _start_task(self, task_id: str) -> list[dict[str, Any]]:
        task = self.tasks[task_id]
        if task.status == "in_progress":
            return []

        task.status = "in_progress"
        details = TASK_DETAILS[task_id] if not task.details_sent else NO_VALUE
        chunk = self._task_chunk(
            task_id,
            status="in_progress",
            details=details,
        )
        if details is not NO_VALUE:
            task.details_sent = True
        return [chunk]

    def _complete_task(
        self,
        task_id: str,
        *,
        output: str | None | object = NO_VALUE,
        sources: list[dict[str, str]] | None | object = NO_VALUE,
    ) -> list[dict[str, Any]]:
        task = self.tasks[task_id]
        if task.status == "complete" and output is NO_VALUE and sources is NO_VALUE:
            return []

        task.status = "complete"

        output_value = output
        if output_value is NO_VALUE and not task.output_sent:
            output_value = TASK_OUTPUTS[task_id]

        sources_value = sources
        if sources_value is NO_VALUE:
            sources_value = NO_VALUE

        chunk = self._task_chunk(
            task_id,
            status="complete",
            output=output_value,
            sources=sources_value,
        )

        if output_value is not NO_VALUE:
            task.output_sent = True
        if sources_value is not NO_VALUE:
            task.sources_sent = True

        return [chunk]

    def _task_chunk(
        self,
        task_id: str,
        *,
        status: str,
        details: str | object = NO_VALUE,
        output: str | object = NO_VALUE,
        sources: list[dict[str, str]] | None | object = NO_VALUE,
    ) -> dict[str, Any]:
        chunk: dict[str, Any] = {
            "type": "task_update",
            "id": task_id,
            "title": TASK_TITLES[task_id],
            "status": status,
        }

        if details is not NO_VALUE and details is not None:
            chunk["details"] = details

        if output is not NO_VALUE and output is not None:
            chunk["output"] = output

        if sources is not NO_VALUE and sources:
            chunk["sources"] = sources

        return chunk


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
        self.plan_closed = False
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

    async def on_node(self, node: str) -> None:
        if node in STREAMING_NODES:
            await self._switch_to_answer_mode()
            return

        await self._append_plan_chunks(self.state.apply_node(node))

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

        if self.answer_stream_ts is None:
            response = await self.client.start_stream(
                channel=self.channel_id,
                thread_ts=self.thread_ts,
                recipient_user_id=self.user_id,
                recipient_team_id=self.team_id,
                markdown_text=markdown_text,
            )
            self.answer_stream_ts = str(response.get("ts") or "").strip() or None
            self.has_streamed_answer = True
            return

        await self.client.append_stream(
            channel=self.channel_id,
            ts=self.answer_stream_ts,
            markdown_text=markdown_text,
        )
        self.has_streamed_answer = True

    async def finish(self, *, answer: str, sources: list[Any]) -> None:
        if self.answer_mode:
            await self.flush_answer_markdown()
            await self._finish_answer_stream(answer=answer, sources=sources)
            return

        await self._finish_plan_stream(answer=answer, sources=sources)

    async def fail(self, message: str) -> None:
        if self.answer_mode:
            await self.flush_answer_markdown()
            if self.answer_stream_ts is not None:
                await self.client.stop_stream(
                    channel=self.channel_id,
                    ts=self.answer_stream_ts,
                    markdown_text=message,
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
            chunks=self.state.fail(message),
            blocks=[],
        )

    async def _switch_to_answer_mode(self) -> None:
        if self.answer_mode:
            return

        await self._append_plan_chunks(self.state.transition_to_answer())
        await self._close_and_delete_plan_stream()
        self.answer_mode = True

    async def _finish_answer_stream(self, *, answer: str, sources: list[Any]) -> None:
        blocks = self.state.build_final_blocks(
            query=self.query,
            answer=answer,
            sources=sources,
            include_answer_body=not self.has_streamed_answer,
        )

        if self.answer_stream_ts is None:
            await self.client.post_message(
                channel=self.channel_id,
                thread_ts=self.thread_ts,
                text=build_plain_fallback_text(answer=answer, sources=sources),
                blocks=blocks,
            )
            return

        await self.client.stop_stream(
            channel=self.channel_id,
            ts=self.answer_stream_ts,
            blocks=blocks,
        )

    async def _finish_plan_stream(self, *, answer: str, sources: list[Any]) -> None:
        blocks = self.state.build_final_blocks(
            query=self.query,
            answer=answer,
            sources=sources,
            include_answer_body=True,
        )

        if self.plan_stream_ts is None:
            await self.client.post_message(
                channel=self.channel_id,
                thread_ts=self.thread_ts,
                text=build_plain_fallback_text(answer=answer, sources=sources),
                blocks=blocks,
            )
            return

        await self.client.stop_stream(
            channel=self.channel_id,
            ts=self.plan_stream_ts,
            chunks=self.state.finish(),
            blocks=blocks,
        )

    async def _close_and_delete_plan_stream(self) -> None:
        if self.plan_stream_ts is None or self.plan_closed:
            return

        try:
            await self.client.stop_stream(
                channel=self.channel_id,
                ts=self.plan_stream_ts,
            )
        finally:
            try:
                await self.client.delete_message(
                    channel=self.channel_id,
                    ts=self.plan_stream_ts,
                )
            finally:
                self.plan_closed = True
                self.plan_stream_ts = None

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
    source_text = build_source_markdown(sources)
    if not source_text:
        return answer
    return f"{answer}\n\nSources:\n{source_text}"


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


def build_source_markdown(sources: list[Any]) -> str:
    lines: list[str] = []

    for source in sources[:MAX_SOURCE_ITEMS]:
        title = read_source_field(source, "title") or "Source"
        url = read_source_field(source, "url")
        if url:
            lines.append(f"• <{url}|{title}>")
            continue
        lines.append(f"• {title}")

    return "\n".join(lines)


def read_source_field(source: Any, field: str) -> str | None:
    if hasattr(source, field):
        value = getattr(source, field)
        return str(value) if value else None

    if isinstance(source, dict):
        value = source.get(field)
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
    value = (text or "").strip()
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."
