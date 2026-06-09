from __future__ import annotations

from unittest import TestCase

from catchup.connectors.slack.ingestion_service import SlackIngestionService
from catchup.connectors.slack.schemas import SlackUser
from catchup.sync.ingestion.document_builders.slack import SlackTransformer


class SlackTransformerBlockBodyTests(TestCase):
    def setUp(self) -> None:
        self.transformer = SlackTransformer(
            {
                "U123": SlackUser(
                    id="U123",
                    name="teammemberb",
                    real_name="Team Member B",
                    display_name="teammemberb",
                )
            }
        )

    def test_plain_text_message_keeps_existing_body(self) -> None:
        message = self.transformer.parse_message(
            {
                "ts": "1777018000.000001",
                "user": "U123",
                "text": "일반 Slack GUI 메시지입니다",
            },
            channel_id="C123",
            channel_name="dev",
        )

        self.assertEqual(message.text, "일반 Slack GUI 메시지입니다")

        document = self.transformer.transform_message(message, "T123")

        self.assertEqual(document.page_content, "일반 Slack GUI 메시지입니다")
        self.assertIn("Message:\n일반 Slack GUI 메시지입니다", document.metadata["contextual_content"])

    def test_bot_message_uses_blocks_beyond_text_fallback(self) -> None:
        message = self.transformer.parse_message(
            {
                "ts": "1776926696.199369",
                "subtype": "bot_message",
                "bot_id": "B123",
                "bot_profile": {"name": "팀원C"},
                "text": "[요청] Agentic RAG 파이프라인 확정 (0.4.2 포함)",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*[요청]* Agentic RAG 파이프라인 확정 (0.4.2 포함)\n*위치* : <https://example.atlassian.net/wiki/x/AQDbBQ>",
                        },
                    },
                    {"type": "divider"},
                    {"type": "section", "text": {"type": "mrkdwn", "text": "*설명*"}},
                    {
                        "type": "rich_text",
                        "elements": [
                            {
                                "type": "rich_text_section",
                                "elements": [
                                    {
                                        "type": "text",
                                        "text": "Agentic RAG 파이프라인 수정 완료했습니다.\n",
                                    },
                                    {"type": "text", "text": "웹 UI와 슬랙봇 답변 생성 과정 스트리밍 참고 부탁드립니다.\n"},
                                    {"type": "user", "user_id": "U123"},
                                ],
                            }
                        ],
                    },
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": "*담당자* : <@U123>\n*기한* : 미정"},
                    },
                    {
                        "type": "actions",
                        "elements": [
                            {"type": "button", "text": {"type": "plain_text", "text": "내 메시지 삭제"}}
                        ],
                    },
                ],
            },
            channel_id="C123",
            channel_name="개발팀",
        )

        document = self.transformer.transform_message(message, "T123")
        contextual_content = document.metadata["contextual_content"]

        self.assertIn("위치 : https://example.atlassian.net/wiki/x/AQDbBQ", contextual_content)
        self.assertIn("Agentic RAG 파이프라인 수정 완료했습니다.", contextual_content)
        self.assertIn("웹 UI와 슬랙봇 답변 생성 과정 스트리밍 참고 부탁드립니다.", contextual_content)
        self.assertIn("담당자 : @Team Member B", contextual_content)
        self.assertNotIn("내 메시지 삭제", contextual_content)

    def test_sections_fields_context_and_attachments_are_extracted(self) -> None:
        body = self.transformer.extract_message_body(
            {
                "text": "Keyword demo",
                "blocks": [
                    {"type": "header", "text": {"type": "plain_text", "text": "Keyword demo"}},
                    {
                        "type": "section",
                        "fields": [
                            {"type": "mrkdwn", "text": "*Owner*\n<@U123>"},
                            {"type": "mrkdwn", "text": "*Due*\n미정"},
                        ],
                    },
                    {"type": "context", "elements": [{"type": "mrkdwn", "text": "Swagger 이슈"}]},
                ],
                "attachments": [
                    {
                        "title": "API Docs",
                        "title_link": "https://example.test/docs",
                        "text": "키워드 넣고 검색 버튼 누르면 됩니다!",
                        "fallback": "키워드 넣고 검색 버튼 누르면 됩니다!",
                        "fields": [{"title": "Status", "value": "Ready"}],
                    }
                ],
            }
        )

        self.assertIn("*Owner*\n<@U123>", body)
        self.assertIn("Swagger 이슈", body)
        self.assertIn("API Docs", body)
        self.assertIn("키워드 넣고 검색 버튼 누르면 됩니다!", body)
        self.assertIn("Status: Ready", body)

    def test_reply_uses_same_effective_body_extraction(self) -> None:
        reply = self.transformer.parse_reply(
            {
                "ts": "1777018130.055109",
                "user": "U123",
                "text": "",
                "blocks": [
                    {
                        "type": "rich_text",
                        "elements": [
                            {
                                "type": "rich_text_section",
                                "elements": [
                                    {"type": "user", "user_id": "U123"},
                                    {"type": "text", "text": " Swagger 이슈로 필터링은 하나만 됩니다~"},
                                ],
                            }
                        ],
                    }
                ],
            }
        )

        self.assertEqual(reply.text, "<@U123> Swagger 이슈로 필터링은 하나만 됩니다~")

    def test_rich_text_list_dedupes_against_slack_text_fallback(self) -> None:
        body = self.transformer.extract_message_body(
            {
                "text": (
                    "<@U123> 시험 끝나시면... 이거 디자인 팀에 공유 부탁드립니다!\n\n"
                    "• 단계별로 판단\n"
                    "• 판단별 동작 내용\n"
                    "이게 잘 보일 수 있다면 좋을 것 같습니다~"
                ),
                "blocks": [
                    {
                        "type": "rich_text",
                        "elements": [
                            {
                                "type": "rich_text_section",
                                "elements": [
                                    {"type": "user", "user_id": "U123"},
                                    {
                                        "type": "text",
                                        "text": " 시험 끝나시면... 이거 디자인 팀에 공유 부탁드립니다!\n\n",
                                    },
                                ],
                            },
                            {
                                "type": "rich_text_list",
                                "style": "bullet",
                                "elements": [
                                    {
                                        "type": "rich_text_section",
                                        "elements": [{"type": "text", "text": "단계별로 판단"}],
                                    },
                                    {
                                        "type": "rich_text_section",
                                        "elements": [{"type": "text", "text": "판단별 동작 내용"}],
                                    },
                                ],
                            },
                            {
                                "type": "rich_text_section",
                                "elements": [
                                    {
                                        "type": "text",
                                        "text": "\n이게 잘 보일 수 있다면 좋을 것 같습니다~",
                                    }
                                ],
                            },
                        ],
                    }
                ],
            }
        )

        self.assertEqual(body.count("시험 끝나시면"), 1)
        self.assertEqual(body.count("단계별로 판단"), 1)
        self.assertIn("• 단계별로 판단", body)


class SlackIngestionSkipTests(TestCase):
    def test_short_text_with_long_blocks_is_syncable(self) -> None:
        service = SlackIngestionService(
            repository=object(),
            team_id="T123",
            access_token="xoxb-test",
        )

        should_skip = service._should_skip_message(
            {
                "ts": "1777018027.220269",
                "text": "데모",
                "blocks": [
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": "키워드 넣고 검색 버튼 누르면 됩니다!"},
                    }
                ],
            }
        )

        self.assertFalse(should_skip)

    def test_join_leave_subtypes_are_still_skipped(self) -> None:
        service = SlackIngestionService(
            repository=object(),
            team_id="T123",
            access_token="xoxb-test",
        )

        self.assertTrue(
            service._should_skip_message(
                {
                    "subtype": "channel_join",
                    "text": "사용자가 채널에 참여했습니다. 충분히 긴 텍스트입니다.",
                    "blocks": [
                        {
                            "type": "section",
                            "text": {"type": "mrkdwn", "text": "저장되면 안 됩니다."},
                        }
                    ],
                }
            )
        )
