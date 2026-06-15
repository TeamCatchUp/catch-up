from __future__ import annotations

from unittest import TestCase

from catchup.connectors.slack.schemas import SlackUser
from catchup.sync.ingestion.adapters.slack.message_base import SlackMessageAdapterBase
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
        self.assertIn(
            "Message:\n일반 Slack GUI 메시지입니다",
            document.metadata["contextual_content"],
        )

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
                                    {
                                        "type": "text",
                                        "text": "웹 UI와 슬랙봇 답변 생성 과정 스트리밍 참고 부탁드립니다.\n",
                                    },
                                    {"type": "user", "user_id": "U123"},
                                ],
                            }
                        ],
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*담당자* : <@U123>\n*기한* : 미정",
                        },
                    },
                    {
                        "type": "actions",
                        "elements": [
                            {
                                "type": "button",
                                "text": {
                                    "type": "plain_text",
                                    "text": "내 메시지 삭제",
                                },
                            }
                        ],
                    },
                ],
            },
            channel_id="C123",
            channel_name="개발팀",
        )

        document = self.transformer.transform_message(message, "T123")
        contextual_content = document.metadata["contextual_content"]

        self.assertIn(
            "위치 : https://example.atlassian.net/wiki/x/AQDbBQ",
            contextual_content,
        )
        self.assertIn("Agentic RAG 파이프라인 수정 완료했습니다.", contextual_content)
        self.assertIn(
            "웹 UI와 슬랙봇 답변 생성 과정 스트리밍 참고 부탁드립니다.",
            contextual_content,
        )
        self.assertIn("담당자 : @Team Member B", contextual_content)
        self.assertNotIn("내 메시지 삭제", contextual_content)

    def test_sections_fields_context_and_attachments_are_extracted(self) -> None:
        body = self.transformer.extract_message_body(
            {
                "text": "Keyword demo",
                "blocks": [
                    {
                        "type": "header",
                        "text": {"type": "plain_text", "text": "Keyword demo"},
                    },
                    {
                        "type": "section",
                        "fields": [
                            {"type": "mrkdwn", "text": "*Owner*\n<@U123>"},
                            {"type": "mrkdwn", "text": "*Due*\n미정"},
                        ],
                    },
                    {
                        "type": "context",
                        "elements": [{"type": "mrkdwn", "text": "Swagger 이슈"}],
                    },
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
                                    {
                                        "type": "text",
                                        "text": " Swagger 이슈로 필터링은 하나만 됩니다~",
                                    },
                                ],
                            }
                        ],
                    }
                ],
            }
        )

        self.assertEqual(reply.text, "<@U123> Swagger 이슈로 필터링은 하나만 됩니다~")

    def test_message_and_reply_preserve_slack_file_access_fields(self) -> None:
        file_payload = {
            "id": "F123",
            "name": "migration-plan.pdf",
            "title": "Migration plan",
            "filetype": "pdf",
            "mimetype": "application/pdf",
            "pretty_type": "PDF",
            "size": 184233,
            "url_private": "https://files.slack.com/files-pri/T123-F123/migration-plan.pdf",
            "url_private_download": (
                "https://files.slack.com/files-pri/T123-F123/download/migration-plan.pdf"
            ),
            "permalink": "https://acme.slack.com/files/U123/F123/migration-plan.pdf",
            "permalink_public": "https://slack-files.com/T123-F123",
            "preview": "Migration plan preview",
            "initial_comment": "Please review before backfill.",
            "mode": "hosted",
            "is_external": False,
            "external_type": None,
            "file_access": "visible",
        }

        message = self.transformer.parse_message(
            {
                "ts": "1777018130.055109",
                "user": "U123",
                "text": "Attached migration plan",
                "files": [file_payload],
                "attachments": [
                    {
                        "id": 1,
                        "title": "Preview",
                        "title_link": "https://example.test/preview",
                        "image_url": "https://example.test/image.png",
                        "thumb_url": "https://example.test/thumb.png",
                        "app_id": "A123",
                        "app_unfurl_url": "https://example.test/unfurl",
                    }
                ],
            },
            channel_id="C123",
            channel_name="dev",
        )
        reply = self.transformer.parse_reply(
            {
                "ts": "1777018131.055109",
                "user": "U123",
                "text": "Reply file",
                "files": [file_payload | {"file_access": "check_file_info"}],
            }
        )

        message_file = message.files[0]
        self.assertEqual(message_file.url_private, file_payload["url_private"])
        self.assertEqual(
            message_file.url_private_download,
            file_payload["url_private_download"],
        )
        self.assertEqual(
            message_file.permalink_public, file_payload["permalink_public"]
        )
        self.assertEqual(message_file.file_access, "visible")
        self.assertEqual(message_file.preview, "Migration plan preview")
        self.assertEqual(
            message.attachments[0].image_url, "https://example.test/image.png"
        )
        self.assertEqual(
            message.attachments[0].app_unfurl_url, "https://example.test/unfurl"
        )
        self.assertEqual(reply.files[0].file_access, "check_file_info")
        self.assertEqual(
            reply.files[0].url_private_download, file_payload["url_private_download"]
        )

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
                                        "elements": [
                                            {"type": "text", "text": "단계별로 판단"}
                                        ],
                                    },
                                    {
                                        "type": "rich_text_section",
                                        "elements": [
                                            {"type": "text", "text": "판단별 동작 내용"}
                                        ],
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
    def test_short_text_is_not_skipped_by_length(self) -> None:
        adapter = SlackMessageAdapterBase(
            client=object(),
            repository=object(),
            team_id="T123",
        )

        should_skip = adapter._should_skip_message_subtype(
            {"ts": "1777018027.220269", "text": "흠.."}
        )

        self.assertFalse(should_skip)

    def test_join_leave_subtypes_are_still_skipped(self) -> None:
        adapter = SlackMessageAdapterBase(
            client=object(),
            repository=object(),
            team_id="T123",
        )

        self.assertTrue(
            adapter._should_skip_message_subtype(
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
