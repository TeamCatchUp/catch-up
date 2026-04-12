from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog

from catchup.connectors.slack.client import SlackApiClientWrapper

logger = structlog.get_logger(__name__)

# 최상단 노출 텍스트
PLAN_TITLE = "Catch Up이 답변을 준비하고 있어요"
PLAN_COMPLETED_TITLE = "Catch Up이 답변을 완성했어요 :)"

# section fallback 렌더링 제약조건
MAX_SECTION_TEXT = 2900
# Slack markdown block 누적 렌더링 제약조건
MAX_MARKDOWN_BLOCK_TEXT = 12000

# 최종 응답에 포함시킬 출처 URL 개수
MAX_SOURCE_ITEMS = 10

# 스트리밍 버퍼링 크기
MARKDOWN_FLUSH_SIZE = 120

# Plan Block Kit 노출 순서
TASK_ORDER = ("route", "search", "rerank", "answer")

# 각 노드에서의 진행중 텍스트
TASK_TITLES = {
    "route": "질문의 의도를 파악하고 있어요",
    "search": "사내 기록을 꼼꼼히 살펴보는 중이에요",
    "rerank": "꼭 필요한 내용만 추려볼게요",
    "answer": "최종 답변을 작성중 ...",
}

# 노드 완료 시 노출 텍스트
TASK_OUTPUTS = {
    "route": "질문을 이해했어요",
    "search": "관련 기록을 모아왔어요",
    "rerank": "핵심 5건을 골랐어요",
    "answer": "답변을 마무리했어요",
}

# search에 해당하는 노드 목록
SEARCH_NODES = {
    "search_vector_db",
    "expand_graph_context",
    "fetch_details_after_graph_context_expansion",
    "fallback_cypher_query",
}

NO_VALUE = object()


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
    status: str = "pending"
    details_sent: bool = False
    output_sent: bool = False
    sources_sent: bool = False


class SlackPlanState:
    def __init__(self) -> None:
        self.tasks = {task_id: TaskState() for task_id in TASK_ORDER}
        # UI 노출 관련도 높은 출처
        self.top_sources: list[Any] = []

    def build_initial_chunks(self) -> list[dict[str, Any]]:
        """Initial Plan Block Kit Skeleton"""
        chunks: list[dict[str, Any]] = [build_plan_title_chunk(PLAN_TITLE)]
        chunks.extend(self._task_chunk(task_id, status="pending") for task_id in TASK_ORDER)
        return chunks

    def apply_node(self, node: str) -> list[dict[str, Any]]:
        """RAG Pipeline Node -> Task Block"""
        if node == "route":
            return self._start_task("route")

        if node in {"rewrite", "generate_vector_queries"}:
            return self._complete_task("route")

        if node in SEARCH_NODES:
            return self._move_to("search", complete_task_ids=("route",))

        if node == "rerank":
            return self._move_to("rerank", complete_task_ids=("search",))

        # chitchat 노드 진입시 모든 Task 완료 처리 
        if node == "chitchat":
            chunks: list[dict[str, Any]] = []
            chunks.extend(self._complete_task("route"))
            chunks.extend(self._complete_task("search", output="검색 단계를 생략했습니다."))
            chunks.extend(self._complete_task("rerank", output="핵심 문서 선별 단계를 생략했습니다."))
            chunks.extend(self._start_task("answer"))
            return chunks

        return []

    def apply_sources(self, sources: list[Any]) -> list[dict[str, Any]]:
        """rerank node 결과를 받아서 MAX_SOURCE_ITEMS만큼 rerank Task Output으로 노출"""
        if not sources:
            return []

        previous_task_sources = build_task_sources(self.top_sources)
        self.top_sources = list(sources[:MAX_SOURCE_ITEMS])
        current_task_sources = build_task_sources(self.top_sources)
        if self.tasks["rerank"].output_sent and current_task_sources == previous_task_sources:
            return []

        rerank_output = f"핵심 {len(self.top_sources)}건을 골랐어요"

        updates: list[dict[str, Any]] = []
        updates.extend(self._complete_task("search"))
        updates.extend(
            self._complete_task(
                "rerank",
                output=rerank_output,
            )
        )
        return updates

    def transition_to_answer(self) -> list[dict[str, Any]]:
        """Plan UI를 유지한 채 answer 단계로 넘어가도록 선행 task를 정리"""
        updates: list[dict[str, Any]] = []
        updates.extend(self._complete_task("search"))
        if self.top_sources:
            updates.extend(
                self._complete_task(
                    "rerank",
                    output=f"핵심 {len(self.top_sources)}건을 골랐어요",
                )
            )
        else:
            updates.extend(self._complete_task_without_output("rerank"))
        updates.extend(self._start_task("answer"))
        return updates

    def finish(self) -> list[dict[str, Any]]:
        return [build_plan_title_chunk(PLAN_COMPLETED_TITLE), *self._complete_task("answer")]

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
        action_links: dict[str, str] | None = None,
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
        if not final_markdown and not action_links:
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
        blocks.extend(build_action_blocks(action_links))
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
        chunk = self._task_chunk(
            task_id,
            status="in_progress",
        )
        return [chunk]

    def _complete_task_without_output(self, task_id: str) -> list[dict[str, Any]]:
        task = self.tasks[task_id]
        if task.status == "complete":
            return []

        task.status = "complete"
        return [
            self._task_chunk(
                task_id,
                status="complete",
            )
        ]

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
        if node in {"generate_final_answer", "generate_final_answer_fast"}:
            await self._switch_to_answer_mode(self.state.transition_to_answer())
            return

        if node == "chitchat":
            await self._switch_to_answer_mode(self.state.apply_node("chitchat"))
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
        action_links: Any = None,
    ) -> None:
        # answer_mode 여부에 따라 같은 ts를 종료할지, plan-only ts를 종료할지 갈린다.
        if self.answer_mode:
            await self.flush_answer_markdown()
            await self._finish_answer_stream(
                answer=answer,
                sources=sources,
                action_links=action_links,
            )
            return

        await self._finish_plan_stream(
            answer=answer,
            sources=sources,
            action_links=action_links,
        )

    async def fail(self, message: str) -> None:
        if self.answer_mode:
            await self.flush_answer_markdown()
            if self.answer_stream_ts is not None:
                failure_chunks = [build_markdown_text_chunk(message), *self.state.fail(message)]
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
            chunks=self.state.fail(message),
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
        action_links: Any = None,
    ) -> None:
        visible_sources = self.state.top_sources or sources
        blocks = self.state.build_final_blocks(
            query=self.query,
            answer=answer,
            sources=sources,
            include_answer_body=not self.has_streamed_answer,
            action_links=normalize_action_links(action_links),
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
        action_links: Any = None,
    ) -> None:
        visible_sources = self.state.top_sources or sources
        blocks = self.state.build_final_blocks(
            query=self.query,
            answer=answer,
            sources=sources,
            include_answer_body=True,
            action_links=normalize_action_links(action_links),
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


def normalize_action_links(action_links: Any) -> dict[str, str] | None:
    # orchestrator dataclass/dict 어느 쪽이 와도 renderer가 동일한 형태로 받게 맞춘다.
    if action_links is None:
        return None
    if isinstance(action_links, dict):
        return {key: value for key, value in action_links.items() if value}
    normalized: dict[str, str] = {}
    for key in ("detail_url", "helpful_value", "not_helpful_value"):
        value = getattr(action_links, key, None)
        if value:
            normalized[key] = value
    return normalized or None


def build_action_blocks(action_links: dict[str, str] | None) -> list[dict[str, Any]]:
    if not action_links:
        return []

    # 상세보기와 피드백 버튼은 본문 아래의 별도 블록으로 고정 배치한다.
    blocks: list[dict[str, Any]] = [{"type": "divider"}]
    detail_url = action_links.get("detail_url")
    if detail_url:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "답변이 도움이 됐나요?",
                },
                "accessory": {
                    "type": "button",
                    "action_id": "view_detail",
                    "text": {
                        "type": "plain_text",
                        "text": "Catch Up에서 자세히 보기",
                        "emoji": False,
                    },
                    "url": detail_url,
                },
            }
        )

    feedback_buttons: list[dict[str, Any]] = []
    helpful_value = action_links.get("helpful_value")
    if helpful_value:
        feedback_buttons.append(
            {
                "type": "button",
                "action_id": "feedback_helpful",
                "text": {
                    "type": "plain_text",
                    "text": "도움됐어요",
                    "emoji": False,
                },
                "style": "primary",
                "value": helpful_value,
            }
        )
    not_helpful_value = action_links.get("not_helpful_value")
    if not_helpful_value:
        feedback_buttons.append(
            {
                "type": "button",
                "action_id": "feedback_not_helpful",
                "text": {
                    "type": "plain_text",
                    "text": "아쉬워요",
                    "emoji": False,
                },
                "style": "danger",
                "value": not_helpful_value,
            }
        )

    if feedback_buttons:
        blocks.append(
            {
                "type": "actions",
                "elements": feedback_buttons,
            }
        )

    return blocks


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
    value = (text or "").strip()
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."
