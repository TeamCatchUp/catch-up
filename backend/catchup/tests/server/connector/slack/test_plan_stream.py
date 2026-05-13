from __future__ import annotations

from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock

from catchup.chat.schemas import ChatStreamingProcessResponse
from catchup.server.connector.slack.plan_stream import PLAN_PLACEHOLDER_TASK_ID
from catchup.server.connector.slack.plan_stream import PLAN_PLACEHOLDER_TASK_TITLE
from catchup.server.connector.slack.plan_stream import PLAN_TITLE
from catchup.server.connector.slack.plan_stream import SlackPlanResponder
from catchup.server.connector.slack.plan_stream import SlackPlanState
from catchup.server.connector.slack.plan_stream import format_source_link


def _process(
    *,
    status: str,
    node: str = "standard_agent",
    reasoning: str | None = None,
) -> ChatStreamingProcessResponse:
    return ChatStreamingProcessResponse(
        status=status,
        node=node,
        reasoning=reasoning,
    )


class SlackPlanStateTests(IsolatedAsyncioTestCase):
    def test_source_link_normalizes_multiline_title(self) -> None:
        link = format_source_link(
            {
                "title": "@팀원D created a Task CATDEV-387 프론트 채널톡 임베딩 화면 퍼블리싱\n"
                "@팀원D created a Task...",
                "url": "https://example.slack.com/archives/C00000001/p1777183681984109",
            }
        )

        self.assertEqual(
            link,
            "[@팀원D created a Task CATDEV-387 프론트 채널톡 임베딩 화면 퍼블리싱 @팀원D created a Task...](https://example.slack.com/archives/C00000001/p1777183681984109)",
        )

    def test_initial_plan_contains_only_container_title(self) -> None:
        state = SlackPlanState()

        self.assertEqual(
            state.build_initial_chunks(),
            [
                {"type": "plan_update", "title": PLAN_TITLE},
                {
                    "type": "task_update",
                    "id": PLAN_PLACEHOLDER_TASK_ID,
                    "title": PLAN_PLACEHOLDER_TASK_TITLE,
                    "status": "pending",
                },
            ],
        )

    def test_in_progress_without_reasoning_starts_placeholder_task(self) -> None:
        state = SlackPlanState()

        chunks = state.apply_process(_process(status="in_progress", reasoning=None))

        self.assertEqual(
            chunks,
            [
                {
                    "type": "task_update",
                    "id": PLAN_PLACEHOLDER_TASK_ID,
                    "title": PLAN_PLACEHOLDER_TASK_TITLE,
                    "status": "in_progress",
                }
            ],
        )

    def test_completed_without_reasoning_is_ignored(self) -> None:
        state = SlackPlanState()

        chunks = state.apply_process(_process(status="completed", reasoning=None))

        self.assertEqual(chunks, [])
        self.assertEqual(state.tasks, {})

    def test_in_progress_reasoning_starts_timeline_task(self) -> None:
        state = SlackPlanState()

        chunks = state.apply_process(
            _process(status="in_progress", node="rewrite", reasoning="어떤 답을 원하시는지 헤아려볼게요.")
        )

        self.assertEqual(
            chunks,
            [
                {
                    "type": "task_update",
                    "id": "reasoning-1",
                    "title": "어떤 답을 원하시는지 헤아려볼게요.",
                    "status": "in_progress",
                }
            ],
        )

    def test_next_reasoning_auto_completes_open_task(self) -> None:
        state = SlackPlanState()
        state.apply_process(
            _process(status="in_progress", node="rewrite", reasoning="어떤 답을 원하시는지 헤아려볼게요.")
        )

        chunks = state.apply_process(
            _process(status="completed", node="standard_agent", reasoning="문서를 더 찾아보겠습니다.")
        )

        self.assertEqual(
            chunks,
            [
                {
                    "type": "task_update",
                    "id": "reasoning-1",
                    "title": "어떤 답을 원하시는지 헤아려볼게요.",
                    "status": "complete",
                },
                {
                    "type": "task_update",
                    "id": "reasoning-2",
                    "title": "문서를 더 찾아보겠습니다.",
                    "status": "complete",
                },
            ],
        )

    def test_sources_are_stored_but_not_rendered_as_plan_copy(self) -> None:
        state = SlackPlanState()
        source = {"title": "Doc", "url": "https://example.com"}

        chunks = state.apply_sources([source])

        self.assertEqual(chunks, [])
        self.assertEqual(state.top_sources, [source])

    def test_failure_does_not_create_non_reasoning_plan_task(self) -> None:
        state = SlackPlanState()
        state.apply_process(
            _process(status="in_progress", node="rewrite", reasoning="질문을 정리하고 있어요.")
        )

        chunks = state.fail()

        self.assertEqual(
            chunks,
            [
                {
                    "type": "task_update",
                    "id": "reasoning-1",
                    "title": "질문을 정리하고 있어요.",
                    "status": "complete",
                }
            ],
        )
        self.assertEqual(len(state.tasks), 1)

    def test_standard_stream_reasoning_sequence_builds_local_chat_timeline(self) -> None:
        state = SlackPlanState()
        events = [
            _process(
                status="in_progress",
                node="supervisor",
                reasoning=None,
            ),
            _process(
                status="completed",
                node="supervisor",
                reasoning="API 종류를 묻는 일반적인 검색 질문이네요. 문서를 찾아볼게요.",
            ),
            _process(
                status="in_progress",
                node="rewrite",
                reasoning="어떤 답을 원하시는지 헤아려볼게요.",
            ),
            _process(
                status="completed",
                node="rewrite",
                reasoning=None,
            ),
            _process(
                status="completed",
                node="standard_agent",
                reasoning="토큰 사용량 집계 API의 구조와 종류를 찾아보겠습니다.",
            ),
            _process(
                status="in_progress",
                node="tool_executor",
                reasoning=None,
            ),
            _process(
                status="completed",
                node="tool_executor",
                reasoning="120건의 문서를 찾았어요.",
            ),
            _process(
                status="completed",
                node="standard_agent",
                reasoning="API 응답 스키마와 파라미터 구조를 확인하기 위해 추가 검색이 필요합니다.",
            ),
            _process(
                status="completed",
                node="tool_executor",
                reasoning="40건의 문서를 찾았어요.",
            ),
            _process(
                status="completed",
                node="standard_agent",
                reasoning="토큰 사용량 집계 API의 종류, 기능, 파라미터, 응답 스키마, 권한 체계 등 질문에 답변하기 위한 정보가 충분히 수집됐어요.",
            ),
            _process(
                status="in_progress",
                node="rerank",
                reasoning="가져온 65개 자료를 관련도순으로 정리하고 있어요.",
            ),
            _process(
                status="in_progress",
                node="generate_final_answer",
                reasoning=None,
            ),
        ]

        chunks = []
        for event in events[:-1]:
            chunks.extend(state.apply_process(event))
        chunks.extend(state.apply_process(events[-1]))
        chunks.extend(state.transition_to_answer())

        titles = [
            chunk["title"]
            for chunk in chunks
            if chunk["type"] == "task_update" and chunk["status"] in {"in_progress", "complete"}
        ]

        self.assertEqual(
            titles,
            [
                PLAN_PLACEHOLDER_TASK_TITLE,
                "API 종류를 묻는 일반적인 검색 질문이네요. 문서를 찾아볼게요.",
                "어떤 답을 원하시는지 헤아려볼게요.",
                "어떤 답을 원하시는지 헤아려볼게요.",
                "토큰 사용량 집계 API의 구조와 종류를 찾아보겠습니다.",
                PLAN_PLACEHOLDER_TASK_TITLE,
                "120건의 문서를 찾았어요.",
                "API 응답 스키마와 파라미터 구조를 확인하기 위해 추가 검색이 필요합니다.",
                "40건의 문서를 찾았어요.",
                "토큰 사용량 집계 API의 종류, 기능, 파라미터, 응답 스키마, 권한 체계 등 질문에 답변하기 위한 정보가 충분히 수집됐어요.",
                "가져온 65개 자료를 관련도순으로 정리하고 있어요.",
                "가져온 65개 자료를 관련도순으로 정리하고 있어요.",
            ],
        )
        self.assertTrue(all(not title.endswith("_agent") for title in titles))


class SlackPlanResponderTests(IsolatedAsyncioTestCase):
    async def test_start_sends_visible_empty_plan_placeholder_immediately(self) -> None:
        client = AsyncMock()
        client.start_stream.return_value = {"ts": "123.456"}

        responder = await SlackPlanResponder.start(
            client=client,
            channel_id="C123",
            thread_ts="1.0",
            team_id="T123",
            user_id="U123",
            query="question",
        )

        client.start_stream.assert_awaited_once_with(
            channel="C123",
            thread_ts="1.0",
            recipient_user_id="U123",
            recipient_team_id="T123",
            task_display_mode="plan",
            chunks=[
                {"type": "plan_update", "title": PLAN_TITLE},
                {
                    "type": "task_update",
                    "id": PLAN_PLACEHOLDER_TASK_ID,
                    "title": PLAN_PLACEHOLDER_TASK_TITLE,
                    "status": "pending",
                },
            ],
        )
        self.assertEqual(responder.plan_stream_ts, "123.456")

    async def test_first_reasoning_replaces_initial_placeholder_task(self) -> None:
        client = AsyncMock()
        client.start_stream.return_value = {"ts": "123.456"}
        responder = await SlackPlanResponder.start(
            client=client,
            channel_id="C123",
            thread_ts="1.0",
            team_id="T123",
            user_id="U123",
            query="question",
        )

        await responder.on_process(
            _process(
                status="completed",
                node="supervisor",
                reasoning="API 종류를 묻는 일반적인 검색 질문이네요. 문서를 찾아볼게요.",
            )
        )

        client.append_stream.assert_awaited_once_with(
            channel="C123",
            ts="123.456",
            chunks=[
                {
                    "type": "task_update",
                    "id": PLAN_PLACEHOLDER_TASK_ID,
                    "title": "API 종류를 묻는 일반적인 검색 질문이네요. 문서를 찾아볼게요.",
                    "status": "complete",
                }
            ],
        )

    async def test_placeholder_in_progress_is_replaced_by_first_reasoning(self) -> None:
        client = AsyncMock()
        client.start_stream.return_value = {"ts": "123.456"}
        responder = await SlackPlanResponder.start(
            client=client,
            channel_id="C123",
            thread_ts="1.0",
            team_id="T123",
            user_id="U123",
            query="question",
        )

        await responder.on_process(
            _process(status="in_progress", node="supervisor", reasoning=None)
        )
        await responder.on_process(
            _process(
                status="completed",
                node="supervisor",
                reasoning="API 종류를 묻는 일반적인 검색 질문이네요. 문서를 찾아볼게요.",
            )
        )

        self.assertEqual(client.append_stream.await_count, 2)
        self.assertEqual(
            client.append_stream.await_args_list[0].kwargs["chunks"],
            [
                {
                    "type": "task_update",
                    "id": PLAN_PLACEHOLDER_TASK_ID,
                    "title": PLAN_PLACEHOLDER_TASK_TITLE,
                    "status": "in_progress",
                }
            ],
        )
        self.assertEqual(
            client.append_stream.await_args_list[1].kwargs["chunks"],
            [
                {
                    "type": "task_update",
                    "id": PLAN_PLACEHOLDER_TASK_ID,
                    "title": "API 종류를 묻는 일반적인 검색 질문이네요. 문서를 찾아볼게요.",
                    "status": "complete",
                }
            ],
        )

    async def test_final_answer_node_switches_to_answer_mode_without_node_copy(self) -> None:
        client = AsyncMock()
        responder = SlackPlanResponder(
            client=client,
            channel_id="C123",
            thread_ts="1.0",
            team_id="T123",
            user_id="U123",
            query="question",
            plan_stream_ts="123.456",
        )
        await responder.on_process(
            _process(status="in_progress", node="rewrite", reasoning="질문을 정리하고 있어요.")
        )
        client.append_stream.reset_mock()

        await responder.on_process(
            _process(status="in_progress", node="generate_final_answer", reasoning=None)
        )

        self.assertTrue(responder.answer_mode)
        client.append_stream.assert_awaited_once_with(
            channel="C123",
            ts="123.456",
            chunks=[
                {
                    "type": "task_update",
                    "id": "reasoning-1",
                    "title": "질문을 정리하고 있어요.",
                    "status": "complete",
                }
            ],
        )

    async def test_final_answer_node_preserves_reasoning_before_answer_mode(self) -> None:
        client = AsyncMock()
        responder = SlackPlanResponder(
            client=client,
            channel_id="C123",
            thread_ts="1.0",
            team_id="T123",
            user_id="U123",
            query="question",
            plan_stream_ts="123.456",
        )

        await responder.on_process(
            _process(status="in_progress", node="generate_final_answer", reasoning="답변을 정리하고 있어요.")
        )

        self.assertTrue(responder.answer_mode)
        client.append_stream.assert_awaited_once_with(
            channel="C123",
            ts="123.456",
            chunks=[
                {
                    "type": "task_update",
                    "id": "reasoning-1",
                    "title": "답변을 정리하고 있어요.",
                    "status": "in_progress",
                },
                {
                    "type": "task_update",
                    "id": "reasoning-1",
                    "title": "답변을 정리하고 있어요.",
                    "status": "complete",
                },
            ],
        )
