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

TASK_ORDER = ("route", "rewrite", "search", "rerank", "grade", "answer")

TASK_TITLES = {
    "route": "질문의 의도를 파악하고 있습니다",
    "rewrite": "검색을 준비하고 있습니다",
    "search": "사내 지식을 살펴보고 있습니다",
    "rerank": "중요한 문서만 고르고 있습니다",
    "grade": "검색 품질을 점검하고 있어요",
    "answer": "최종 답변을 작성중 ...",
}

SEARCH_NODES = {
    "search_vector_db",
    "expand_graph_context",
    "fetch_details_after_graph_context_expansion",
    "fallback_cypher_query",
}


@dataclass(slots=True)
class TaskState:
    status: str = "pending"
    details: str | None = None
    output: str | None = None
    sources: list[dict[str, str]] | None = None


class SlackPlanState:
    def __init__(self) -> None:
        self.tasks = {task_id: TaskState() for task_id in TASK_ORDER}
        self.answer_started = False

    def build_initial_chunks(self) -> list[dict[str, Any]]:
        chunks: list[dict[str, Any]] = [{"type": "plan_update", "title": PLAN_TITLE}]

        for task_id in TASK_ORDER:
            chunks.append(self._build_chunk(task_id))

        return chunks

    def apply_node(self, node: str) -> list[dict[str, Any]]:
        if node == "route":
            return self._set_route_in_progress()

        if node in {"rewrite", "generate_vector_queries"}:
            return self._set_rewrite_in_progress(node)

        if node in SEARCH_NODES:
            return self._set_search_in_progress(node)

        if node == "rerank":
            return self._set_rerank_in_progress()

        if node == "grade":
            return self._set_grade_in_progress()

        if node == "generate_final_answer":
            return self._set_answer_in_progress(rag_mode=True)

        if node == "chitchat":
            return self._set_answer_in_progress(rag_mode=False)

        return []

    def apply_sources(self, sources: list[Any]) -> list[dict[str, Any]]:
        if not sources:
            return []

        source_count = min(len(sources), MAX_SOURCE_ITEMS)
        source_refs = build_task_sources(sources)
        updates: list[dict[str, Any]] = []

        updates.extend(
            self._complete_task(
                "search",
                output=f"관련 문서를 수집했습니다.",
            )
        )
        updates.extend(
            self._complete_task(
                "rerank",
                output=f"답변에 참고할 문서 {source_count}건을 골랐습니다.",
                sources=source_refs,
            )
        )

        return updates

    def finish(self) -> list[dict[str, Any]]:
        return self._complete_task(
            "answer",
            output="최종 답변 생성을 마쳤습니다.",
            details=None,
        )

    def fail(self, message: str) -> list[dict[str, Any]]:
        return self._update_task(
            "answer",
            status="error",
            details=message,
            output=None,
        )

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

    def _set_route_in_progress(self) -> list[dict[str, Any]]:
        return self._update_task(
            "route",
            status="in_progress",
            details="질문의 의도를 파악하고 있어요.",
            output=None,
        )

    def _set_rewrite_in_progress(self, node: str) -> list[dict[str, Any]]:
        updates = self._complete_task("route", output="질문 의도 파악을 마쳤습니다.")
        details = (
            "검색 쿼리를 준비하고 있어요."
            if node == "generate_vector_queries"
            else "질문을 검색 친화적으로 정리하고 있어요."
        )
        updates.extend(
            self._update_task(
                "rewrite",
                status="in_progress",
                details=details,
                output=None,
            )
        )
        return updates

    def _set_search_in_progress(self, node: str) -> list[dict[str, Any]]:
        updates = self._complete_task("rewrite", output="검색 준비를 마쳤습니다.")
        details_map = {
            "search_vector_db": "지식 저장소에서 관련 문서를 찾고 있어요.",
            "expand_graph_context": "연관된 지식을 더 넓게 탐색하고 있어요.",
            "fetch_details_after_graph_context_expansion": "확장한 문서의 세부 내용을 읽고 있어요.",
            "fallback_cypher_query": "추가 그래프 질의로 관련 정보를 보강하고 있어요.",
        }
        updates.extend(
            self._update_task(
                "search",
                status="in_progress",
                details=details_map.get(node),
                output=None,
            )
        )
        return updates

    def _set_rerank_in_progress(self) -> list[dict[str, Any]]:
        updates = self._complete_task("search", output="관련 문서 탐색을 마쳤습니다.")
        updates.extend(
            self._update_task(
                "rerank",
                status="in_progress",
                details="중요도가 높은 문서만 추리고 있어요.",
                output=None,
            )
        )
        return updates

    def _set_grade_in_progress(self) -> list[dict[str, Any]]:
        updates = self._complete_task("rerank", output="중요한 문서를 추렸습니다.")
        updates.extend(
            self._update_task(
                "grade",
                status="in_progress",
                details="검색 품질을 점검하고 있어요.",
                output=None,
            )
        )
        return updates

    def _set_answer_in_progress(self, *, rag_mode: bool) -> list[dict[str, Any]]:
        updates: list[dict[str, Any]] = []

        if rag_mode:
            updates.extend(self._complete_task("grade", output="답변에 충분한 문서를 확보했습니다."))
        else:
            updates.extend(self._complete_task("route", output="질문 의도 파악을 마쳤습니다."))
            updates.extend(self._complete_task("rewrite", output="이번 질문은 검색 없이 바로 답변할 수 있습니다."))
            updates.extend(self._complete_task("search", output="검색 단계를 생략했습니다."))
            updates.extend(self._complete_task("rerank", output="재정렬 단계를 생략했습니다."))
            updates.extend(self._complete_task("grade", output="품질 점검 단계를 생략했습니다."))

        updates.extend(
            self._update_task(
                "answer",
                status="in_progress",
                details="문서를 참고하여 답변을 작성하고 있어요.",
                output=None,
            )
        )
        self.answer_started = True
        return updates

    def _complete_task(
        self,
        task_id: str,
        *,
        output: str | None,
        details: str | None = None,
        sources: list[dict[str, str]] | None = None,
    ) -> list[dict[str, Any]]:
        return self._update_task(
            task_id,
            status="complete",
            details=details,
            output=output,
            sources=sources,
        )

    def _update_task(
        self,
        task_id: str,
        *,
        status: str,
        details: str | None,
        output: str | None,
        sources: list[dict[str, str]] | None = None,
    ) -> list[dict[str, Any]]:
        current = self.tasks[task_id]
        normalized_sources = sources or None

        if (
            current.status == status
            and current.details == details
            and current.output == output
            and current.sources == normalized_sources
        ):
            return []

        current.status = status
        current.details = details
        current.output = output
        current.sources = normalized_sources
        return [self._build_chunk(task_id)]

    def _build_chunk(self, task_id: str) -> dict[str, Any]:
        current = self.tasks[task_id]
        chunk: dict[str, Any] = {
            "type": "task_update",
            "id": task_id,
            "title": TASK_TITLES[task_id],
            "status": current.status,
        }

        if current.details:
            chunk["details"] = current.details

        if current.output:
            chunk["output"] = current.output

        if current.sources:
            chunk["sources"] = current.sources

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
        stream_ts: str | None,
    ) -> None:
        self.client = client
        self.channel_id = channel_id
        self.thread_ts = thread_ts
        self.team_id = team_id
        self.user_id = user_id
        self.query = query
        self.stream_ts = stream_ts
        self.state = SlackPlanState()
        self.markdown_buffer = ""
        self.has_streamed_answer = False

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
        stream_ts: str | None = None
        state = SlackPlanState()

        try:
            response = await client.start_stream(
                channel=channel_id,
                thread_ts=thread_ts,
                recipient_user_id=user_id,
                recipient_team_id=team_id,
                task_display_mode="plan",
                chunks=state.build_initial_chunks(),
            )
            stream_ts = str(response.get("ts") or "").strip() or None
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
            stream_ts=stream_ts,
        )
        responder.state = state
        return responder

    async def on_node(self, node: str) -> None:
        await self._append_chunks(self.state.apply_node(node))

    async def on_sources(self, sources: list[Any]) -> None:
        await self._append_chunks(self.state.apply_sources(sources))

    async def finish(self, *, answer: str, sources: list[Any]) -> None:
        await self.flush_markdown()
        blocks = self.state.build_final_blocks(
            query=self.query,
            answer=answer,
            sources=sources,
            include_answer_body=not self.has_streamed_answer,
        )

        if self.stream_ts is None:
            await self.client.post_message(
                channel=self.channel_id,
                thread_ts=self.thread_ts,
                text=build_plain_fallback_text(answer=answer, sources=sources),
                blocks=blocks,
            )
            return

        try:
            await self.client.stop_stream(
                channel=self.channel_id,
                ts=self.stream_ts,
                chunks=self.state.finish(),
                blocks=blocks,
            )
        except Exception:
            logger.exception(
                "slack_stream_stop_failed",
                channel_id=self.channel_id,
                thread_ts=self.thread_ts,
                stream_ts=self.stream_ts,
            )
            await self.client.post_message(
                channel=self.channel_id,
                thread_ts=self.thread_ts,
                text=build_plain_fallback_text(answer=answer, sources=sources),
                blocks=blocks,
            )

    async def fail(self, message: str) -> None:
        await self.flush_markdown()
        if self.stream_ts is None:
            await self.client.post_message(
                channel=self.channel_id,
                thread_ts=self.thread_ts,
                text=message,
            )
            return

        try:
            await self.client.stop_stream(
                channel=self.channel_id,
                ts=self.stream_ts,
                chunks=self.state.fail(message),
                blocks=[],
            )
        except Exception:
            logger.exception(
                "slack_stream_fail_stop_failed",
                channel_id=self.channel_id,
                thread_ts=self.thread_ts,
                stream_ts=self.stream_ts,
            )
            await self.client.post_message(
                channel=self.channel_id,
                thread_ts=self.thread_ts,
                text=message,
            )

    async def append_markdown(self, text: str) -> None:
        if self.stream_ts is None or not text:
            return

        self.markdown_buffer += text
        if len(self.markdown_buffer) < MARKDOWN_FLUSH_SIZE and not text.endswith(("\n", ".", "!", "?")):
            return

        await self.flush_markdown()

    async def flush_markdown(self) -> None:
        if self.stream_ts is None or not self.markdown_buffer:
            return

        markdown_text = self.markdown_buffer
        self.markdown_buffer = ""
        self.has_streamed_answer = True

        await self.client.append_stream(
            channel=self.channel_id,
            ts=self.stream_ts,
            markdown_text=markdown_text,
        )

    async def _append_chunks(self, chunks: list[dict[str, Any]]) -> None:
        if self.stream_ts is None or not chunks:
            return

        await self.client.append_stream(
            channel=self.channel_id,
            ts=self.stream_ts,
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
