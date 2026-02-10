"""
Slack 엔티티 → LangChain Document 변환기

Slack API 응답을 Pydantic Schema로 파싱하고,
PGVector 저장을 위한 LangChain Document로 변환.

변환 흐름:
    1. Slack API 응답 (dict) → Pydantic Schema
    2. Pydantic Schema → LangChain Document (page_content + metadata)

사용법:
    user_cache = {user_id: SlackUser(...), ...}
    transformer = SlackTransformer(user_cache)

    # Message 변환
    doc = transformer.transform_message(message_schema, workspace_id)
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from langchain_core.documents import Document

from catchup.connectors.base import format_file_size
from catchup.connectors.slack.schemas import (
    SlackAttachment,
    SlackChannel,
    SlackFile,
    SlackFileRef,
    SlackMessage,
    SlackReaction,
    SlackThreadReply,
    SlackUser,
    SlackUserProfile,
    SlackWorkspace,
)
from catchup.configs.config import settings


class SlackTransformer:
    """
    Slack 엔티티 → LangChain Document 변환기

    Attributes:
        user_cache: user_id → SlackUser 매핑 (멘션 변환용)
    """

    def __init__(self, user_cache: dict[str, SlackUser] | None = None):
        """
        SlackTransformer 초기화

        Args:
            user_cache: user_id → SlackUser 매핑 딕셔너리
        """
        self.user_cache = user_cache or {}

    # ================================================================
    # Message 변환
    # ================================================================

    def transform_message(
        self,
        message: SlackMessage,
        workspace_id: str,
    ) -> Document:
        """
        SlackMessage → LangChain Document

        Args:
            message: 변환할 메시지 스키마
            workspace_id: Slack Workspace ID

        Returns:
            LangChain Document with page_content and metadata
        """
        # page_content: 임베딩용 (의미 중심 텍스트)
        page_content = self._build_message_embedding_content(message)

        # display_content: LLM 답변 생성용 (기존 포맷)
        display_content = self._build_message_display_content(message)

        metadata = self._build_message_metadata(message, workspace_id)
        metadata["display_content"] = display_content

        doc_id = f"slack:message:{workspace_id}:{message.channel_id}:{message.ts}"

        return Document(
            page_content=page_content,
            metadata=metadata,
            id=doc_id,
        )

    def _build_message_embedding_content(self, message: SlackMessage) -> str:
        """
        Message용 임베딩 텍스트 생성 (의미 중심)

        포함: text(본문), replies(본문만)
        제외: 시간, Author, Channel, Replies 수, Mentioned, Reacted, Attached, Links
        """
        parts = []

        # 1. 메시지 본문
        text = self._parse_slack_markdown(message.text)
        if text:
            parts.append(text)

        # 2. Replies 본문 (author 제외)
        for reply in message.replies:
            reply_text = self._parse_slack_markdown(reply.text)
            if reply_text:
                parts.append(reply_text)

        return "\n\n".join(parts)

    def _build_message_display_content(self, message: SlackMessage) -> str:
        """
        메시지 display_content 생성 - LLM 답변 생성용

        Format (Context 먼저, 본문 나중):
            [2024-02-05 09:30:00]
            Author: 홍길동
            Channel: #general
            Replies: 8
            Mentioned: 김철수, 박영희
            Reacted: 이민수, 팀원A
            Attached: document.pdf (PDF, 2.5 MB)
            Links: [연동 가이드](https://notion.so/...)

            Message:
            {text with @mentions resolved}

            Recent Replies (3):
            [김철수 at 2024-02-05 10:15]: reply text...
        """
        parts = []

        # === Context Section (메타정보 상단 배치) ===
        timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
        parts.append(f"[{timestamp}]")

        # Author
        author = message.user_real_name or message.user_name or message.bot_name or "Unknown"
        parts.append(f"Author: {author}")

        # Channel
        channel_display = f"#{message.channel_name}" if message.channel_name else f"#{message.channel_id}"
        parts.append(f"Channel: {channel_display}")

        # Replies
        if message.reply_count > 0:
            parts.append(f"Replies: {message.reply_count}")

        # Mentioned (멘션된 사용자)
        if message.mentioned_users:
            mentioned_names = [
                u.real_name or u.name or u.id
                for u in message.mentioned_users
            ]
            parts.append(f"Mentioned: {', '.join(mentioned_names)}")

        # Reacted (리액션한 사용자 - 중복 제거)
        if message.reactions:
            reacted_user_ids = set()
            reacted_names = []
            for reaction in message.reactions:
                for user_id in reaction.users:
                    if user_id not in reacted_user_ids:
                        reacted_user_ids.add(user_id)
                        user = self.user_cache.get(user_id)
                        if user:
                            reacted_names.append(user.real_name or user.name or user_id)
                        else:
                            reacted_names.append(user_id)
            if reacted_names:
                parts.append(f"Reacted: {', '.join(reacted_names)}")

        # Attached (업로드된 파일 - SlackFileRef)
        if message.files:
            file_strs = []
            for f in message.files:
                size_str = format_file_size(f.size) if f.size else ""
                file_type = f.filetype.upper() if f.filetype else "File"
                if size_str:
                    file_strs.append(f"{f.name} ({file_type}, {size_str})")
                else:
                    file_strs.append(f"{f.name} ({file_type})")
            parts.append(f"Attached: {', '.join(file_strs)}")

        # Links (Bot 메시지의 Attachments - 링크/URL)
        if message.attachments:
            link_strs = []
            for att in message.attachments:
                if att.title and att.title_link:
                    link_strs.append(f"[{att.title}]({att.title_link})")
                elif att.title_link:
                    link_strs.append(att.title_link)
                elif att.from_url:
                    link_strs.append(att.from_url)
            if link_strs:
                parts.append(f"Links: {', '.join(link_strs)}")

        parts.append("")  # 빈 줄로 Context와 본문 구분

        # === Message Body ===
        parts.append("Message:")
        parts.append(self._parse_slack_markdown(message.text))

        # Attachment 추가 텍스트/Fields (Bot 메시지 상세 내용)
        if message.attachments:
            for att in message.attachments:
                # 추가 텍스트가 있는 경우
                if att.text:
                    att_text = self._parse_slack_markdown(att.text)
                    if att_text:
                        parts.append(att_text[:300])
                # Fields 정보 (Key-Value 쌍)
                for field in att.fields:
                    field_title = field.get("title", "")
                    field_value = field.get("value", "")
                    if field_title and field_value:
                        parts.append(f"  {field_title}: {field_value}")

        # === Thread Replies (최근 N개) ===
        if message.replies:
            parts.append("")
            parts.append(f"Recent Replies ({len(message.replies)}):")
            for reply in message.replies[-settings.SLACK_THREAD_REPLY_LIMIT:]:
                reply_author = reply.user_real_name or reply.user_name or reply.user_id
                reply_ts = self._ts_to_datetime(reply.ts)
                reply_time = reply_ts.strftime("%Y-%m-%d %H:%M") if reply_ts else "Unknown"
                reply_text = self._parse_slack_markdown(reply.text)
                # 길이 제한 (200자)
                if len(reply_text) > 200:
                    reply_text = reply_text[:200] + "..."
                parts.append(f"[{reply_author} at {reply_time}]: {reply_text}")

        return "\n".join(parts).strip()

    def _build_message_metadata(
        self,
        message: SlackMessage,
        workspace_id: str,
    ) -> dict[str, Any]:
        """메시지 metadata 생성"""
        # Reply 작성자 목록 (중복 제거)
        reply_users = []
        seen_reply_user_ids = set()
        for reply in message.replies:
            if reply.user_id not in seen_reply_user_ids:
                seen_reply_user_ids.add(reply.user_id)
                reply_users.append({
                    "user_id": reply.user_id,
                    "user_name": reply.user_name,
                    "real_name": reply.user_real_name,
                })

        # Reaction 사용자 목록 (중복 제거)
        reacted_users = []
        seen_reacted_user_ids = set()
        for reaction in message.reactions:
            for user_id in reaction.users:
                if user_id not in seen_reacted_user_ids:
                    seen_reacted_user_ids.add(user_id)
                    user = self.user_cache.get(user_id)
                    reacted_users.append({
                        "user_id": user_id,
                        "user_name": user.name if user else None,
                        "real_name": user.real_name if user else None,
                    })

        # Mentioned 사용자 목록
        mentioned_users = [
            {
                "user_id": u.id,
                "user_name": u.name,
                "real_name": u.real_name,
            }
            for u in message.mentioned_users
        ]

        return {
            # === 공통 필수 ===
            "source": "slack",
            "entity_type": "message",
            "url": message.url,
            "summary": self._parse_slack_markdown(message.text),

            # === Slack 식별 ===
            "team_id": workspace_id,
            "channel_id": message.channel_id,
            "channel_name": message.channel_name,
            "ts": message.ts,
            "thread_ts": message.thread_ts,

            # === 메시지 타입 ===
            "message_type": message.message_type,
            "subtype": message.subtype,

            # === 작성자 ===
            "author": {
                "user_id": message.user_id or message.bot_id,
                "user_name": message.user_name or message.bot_name,
                "real_name": message.user_real_name,
            },

            # === 시간 ===
            "created_at": message.created_at.isoformat(),
            "edited_at": message.edited_ts,
            "synced_at": datetime.now(timezone.utc).isoformat(),

            # === Thread 정보 ===
            "reply_count": message.reply_count,
            "latest_reply_ts": message.latest_reply_ts,
            "reply_users": reply_users,

            # === Mentioned 사용자 ===
            "mentioned_users": mentioned_users,

            # === Reactions 사용자 ===
            "reacted_users": reacted_users,

            # === 첨부 파일 ===
            "files": [
                {
                    "id": f.id,
                    "name": f.name,
                    "title": f.title,
                    "filetype": f.filetype,
                    "mimetype": f.mimetype,
                    "size": f.size,
                    "url": f.url_private,
                    "permalink": f.permalink,
                }
                for f in message.files
            ],

            # === Attachments (Bot 메시지 링크 등) ===
            "attachments": [
                {
                    "title": a.title,
                    "title_link": a.title_link,
                    "text": a.text,
                    "service_name": a.service_name,
                    "from_url": a.from_url,
                    "fields": a.fields,
                }
                for a in message.attachments
                if a.title_link or a.from_url  # 링크가 있는 attachment만
            ],

            # === 외부 참조 ===
            "jira_issues": message.jira_issues,
            "github_issues": message.github_issues,
        }

    # ================================================================
    # Channel 변환
    # ================================================================

    def transform_channel(
        self,
        channel: SlackChannel,
        workspace_id: str,
    ) -> Document:
        """
        SlackChannel → LangChain Document
        """
        page_content = self._build_channel_content(channel)
        metadata = self._build_channel_metadata(channel, workspace_id)
        doc_id = f"slack:channel:{workspace_id}:{channel.id}"

        return Document(
            page_content=page_content,
            metadata=metadata,
            id=doc_id,
        )

    def _build_channel_content(self, channel: SlackChannel) -> str:
        """채널 page_content 생성"""
        parts = []

        # 헤더
        channel_type_label = {
            "public": "Public Channel",
            "private": "Private Channel",
            "dm": "Direct Message",
            "mpim": "Group DM",
        }.get(channel.channel_type, "Channel")

        parts.append(f"[{channel_type_label}] #{channel.name}")
        parts.append("")

        # Topic & Purpose
        if channel.topic:
            parts.append(f"Topic: {channel.topic}")
        if channel.purpose:
            parts.append(f"Purpose: {channel.purpose}")

        # Members
        if channel.member_count > 0:
            parts.append(f"Members: {channel.member_count}")

        return "\n".join(parts).strip()

    def _build_channel_metadata(
        self,
        channel: SlackChannel,
        workspace_id: str,
    ) -> dict[str, Any]:
        """채널 metadata 생성"""
        return {
            "source": "slack",
            "entity_type": "channel",
            "team_id": workspace_id,
            "channel_id": channel.id,
            "channel_name": channel.name,
            "channel_type": channel.channel_type,
            "topic": channel.topic,
            "purpose": channel.purpose,
            "creator_id": channel.creator_id,
            "member_count": channel.member_count,
            "is_archived": channel.is_archived,
            "is_private": channel.is_private,
            "created_at": channel.created_at.isoformat(),
            "updated_at": channel.updated_at.isoformat() if channel.updated_at else None,
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }

    # ================================================================
    # User 변환
    # ================================================================

    def transform_user(
        self,
        user: SlackUserProfile,
        workspace_id: str,
    ) -> Document:
        """
        SlackUserProfile → LangChain Document
        """
        page_content = self._build_user_content(user)
        metadata = self._build_user_metadata(user, workspace_id)
        doc_id = f"slack:user:{workspace_id}:{user.id}"

        return Document(
            page_content=page_content,
            metadata=metadata,
            id=doc_id,
        )

    def _build_user_content(self, user: SlackUserProfile) -> str:
        """사용자 page_content 생성"""
        parts = []

        # 이름
        display_name = user.display_name or user.real_name or user.name
        parts.append(f"[User] {display_name} (@{user.name})")
        parts.append("")

        # 프로필
        if user.title:
            parts.append(f"Title: {user.title}")
        if user.email:
            parts.append(f"Email: {user.email}")
        if user.tz_label:
            parts.append(f"Timezone: {user.tz_label}")

        # 상태
        if user.status_emoji or user.status_text:
            status = f"{user.status_emoji or ''} {user.status_text or ''}".strip()
            parts.append(f"Status: {status}")

        # 역할
        roles = []
        if user.is_admin:
            roles.append("Admin")
        if user.is_owner:
            roles.append("Owner")
        if user.is_bot:
            roles.append("Bot")
        if user.is_restricted:
            roles.append("Guest")
        if roles:
            parts.append(f"Roles: {', '.join(roles)}")

        return "\n".join(parts).strip()

    def _build_user_metadata(
        self,
        user: SlackUserProfile,
        workspace_id: str,
    ) -> dict[str, Any]:
        """사용자 metadata 생성"""
        return {
            "source": "slack",
            "entity_type": "user",
            "team_id": workspace_id,
            "user_id": user.id,
            "username": user.name,
            "real_name": user.real_name,
            "display_name": user.display_name,
            "email": user.email,
            "title": user.title,
            "tz": user.tz,
            "tz_label": user.tz_label,
            "is_bot": user.is_bot,
            "is_admin": user.is_admin,
            "is_owner": user.is_owner,
            "is_restricted": user.is_restricted,
            "deleted": user.deleted,
            "avatar_url": user.avatar_url,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None,
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }

    # ================================================================
    # File 변환
    # ================================================================

    def transform_file(
        self,
        file: SlackFile,
        workspace_id: str,
    ) -> Document:
        """
        SlackFile → LangChain Document

        - page_content에 파일명
        - metadata에 다운로드 URL
        """
        page_content = self._build_file_content(file)
        metadata = self._build_file_metadata(file, workspace_id)
        doc_id = f"slack:file:{workspace_id}:{file.id}"

        return Document(
            page_content=page_content,
            metadata=metadata,
            id=doc_id,
        )

    def _build_file_content(self, file: SlackFile) -> str:
        """파일 page_content 생성"""
        parts = []

        # 헤더
        parts.append(f"[File] {file.name}")
        if file.title and file.title != file.name:
            parts.append(f"Title: {file.title}")
        parts.append("")

        # 파일 정보
        parts.append(f"Type: {file.pretty_type or file.filetype}")
        parts.append(f"Size: {format_file_size(file.size)}")

        if file.user_name:
            parts.append(f"Uploaded by: {file.user_name}")

        # 초기 코멘트
        if file.initial_comment:
            parts.append("")
            parts.append("Comment:")
            parts.append(file.initial_comment)

        return "\n".join(parts).strip()

    def _build_file_metadata(
        self,
        file: SlackFile,
        workspace_id: str,
    ) -> dict[str, Any]:
        """파일 metadata 생성"""
        return {
            "source": "slack",
            "entity_type": "file",
            "team_id": workspace_id,
            "file_id": file.id,
            "filename": file.name,
            "title": file.title,
            "filetype": file.filetype,
            "mimetype": file.mimetype,
            "pretty_type": file.pretty_type,
            "size": file.size,
            "user_id": file.user_id,
            "user_name": file.user_name,
            "channel_ids": file.channel_ids,
            "url": file.url_private,
            "url_download": file.url_private_download,
            "permalink": file.permalink,
            "mode": file.mode,
            "is_external": file.is_external,
            "external_type": file.external_type,
            "created_at": file.created_at.isoformat(),
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }

    # ================================================================
    # Workspace 변환
    # ================================================================

    def transform_workspace(self, workspace: SlackWorkspace) -> Document:
        """
        SlackWorkspace → LangChain Document
        """
        page_content = self._build_workspace_content(workspace)
        metadata = self._build_workspace_metadata(workspace)
        doc_id = f"slack:workspace:{workspace.id}"

        return Document(
            page_content=page_content,
            metadata=metadata,
            id=doc_id,
        )

    def _build_workspace_content(self, workspace: SlackWorkspace) -> str:
        """워크스페이스 page_content 생성"""
        parts = []

        parts.append(f"[Workspace] {workspace.name}")
        parts.append(f"Domain: {workspace.domain}.slack.com")
        parts.append(f"URL: {workspace.url}")

        if workspace.email_domain:
            parts.append(f"Email Domain: {workspace.email_domain}")

        if workspace.enterprise_name:
            parts.append(f"Enterprise: {workspace.enterprise_name}")

        return "\n".join(parts).strip()

    def _build_workspace_metadata(self, workspace: SlackWorkspace) -> dict[str, Any]:
        """워크스페이스 metadata 생성"""
        return {
            "source": "slack",
            "entity_type": "workspace",
            "team_id": workspace.id,
            "name": workspace.name,
            "domain": workspace.domain,
            "url": workspace.url,
            "email_domain": workspace.email_domain,
            "icon_url": workspace.icon_url,
            "enterprise_id": workspace.enterprise_id,
            "enterprise_name": workspace.enterprise_name,
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }

    # ================================================================
    # API 응답 파싱 유틸리티
    # ================================================================

    def parse_message(
        self,
        data: dict[str, Any],
        channel_id: str,
        channel_name: str | None = None,
        permalink: str | None = None,
        replies: list[SlackThreadReply] | None = None,
    ) -> SlackMessage:
        """
        Slack API 메시지 응답 → SlackMessage 스키마

        Args:
            data: conversations.history 또는 conversations.replies의 메시지 객체
            channel_id: 채널 ID
            channel_name: 채널 이름
            permalink: 메시지 permalink
            replies: Thread replies (이미 파싱된 경우)

        Returns:
            SlackMessage 스키마
        """
        ts = data.get("ts", "")
        text = data.get("text", "")
        subtype = data.get("subtype")

        # 작성자 정보
        user_id = data.get("user")
        user_info = self.user_cache.get(user_id, SlackUser(id=user_id or "unknown"))
        bot_id = data.get("bot_id")
        bot_profile = data.get("bot_profile", {})

        # Thread 정보
        thread_ts = data.get("thread_ts")
        reply_count = data.get("reply_count", 0)
        reply_users_count = data.get("reply_users_count", 0)
        latest_reply = data.get("latest_reply")

        # 메시지 타입 결정
        if reply_count > 0 and thread_ts == ts:
            message_type = "thread_parent"
        elif data.get("files"):
            message_type = "file_share"
        else:
            message_type = "standard"

        # Reactions 파싱
        reactions = [
            SlackReaction(
                name=r.get("name", ""),
                count=r.get("count", 0),
                users=r.get("users", []),
            )
            for r in data.get("reactions", [])
        ]

        # Files 파싱
        files = [
            SlackFileRef(
                id=f.get("id", ""),
                name=f.get("name", ""),
                title=f.get("title"),
                filetype=f.get("filetype"),
                mimetype=f.get("mimetype"),
                size=f.get("size"),
                url_private=f.get("url_private"),
                permalink=f.get("permalink"),
            )
            for f in data.get("files", [])
        ]

        # Attachments 파싱 (Bot 메시지, 링크 미리보기 등)
        attachments = [
            SlackAttachment(
                id=a.get("id"),
                fallback=a.get("fallback"),
                title=a.get("title"),
                title_link=a.get("title_link"),
                text=a.get("text"),
                pretext=a.get("pretext"),
                author_name=a.get("author_name"),
                author_link=a.get("author_link"),
                service_name=a.get("service_name"),
                from_url=a.get("from_url"),
                footer=a.get("footer"),
                color=a.get("color"),
                fields=a.get("fields", []),
                actions=a.get("actions", []),
            )
            for a in data.get("attachments", [])
        ]

        # Mentioned 사용자 추출
        mentioned_users = self._extract_mentioned_users(text)

        # 외부 참조 추출
        jira_issues, github_prs, github_issues = self._extract_external_refs(text)

        # 시간 변환
        created_at = self._ts_to_datetime(ts)

        return SlackMessage(
            ts=ts,
            channel_id=channel_id,
            channel_name=channel_name,
            url=permalink,
            message_type=message_type,
            text=text,
            subtype=subtype,
            user_id=user_id,
            user_name=user_info.name if user_info else None,
            user_real_name=user_info.real_name if user_info else None,
            bot_id=bot_id,
            bot_name=bot_profile.get("name"),
            thread_ts=thread_ts,
            reply_count=reply_count,
            reply_users_count=reply_users_count,
            latest_reply_ts=latest_reply,
            replies=replies or [],
            reactions=reactions,
            files=files,
            attachments=attachments,
            mentioned_users=mentioned_users,
            created_at=created_at,
            edited_ts=data.get("edited", {}).get("ts"),
            jira_issues=jira_issues,
            github_prs=github_prs,
            github_issues=github_issues,
        )

    def parse_reply(self, data: dict[str, Any]) -> SlackThreadReply:
        """
        Thread Reply 파싱

        Args:
            data: conversations.replies의 개별 메시지 객체

        Returns:
            SlackThreadReply 스키마
        """
        user_id = data.get("user", "")
        user_info = self.user_cache.get(user_id, SlackUser(id=user_id))

        reactions = [
            SlackReaction(
                name=r.get("name", ""),
                count=r.get("count", 0),
                users=r.get("users", []),
            )
            for r in data.get("reactions", [])
        ]

        files = [
            SlackFileRef(
                id=f.get("id", ""),
                name=f.get("name", ""),
                filetype=f.get("filetype"),
                url_private=f.get("url_private"),
            )
            for f in data.get("files", [])
        ]

        return SlackThreadReply(
            ts=data.get("ts", ""),
            user_id=user_id,
            user_name=user_info.name if user_info else None,
            user_real_name=user_info.real_name if user_info else None,
            text=data.get("text", ""),
            reactions=reactions,
            files=files,
        )

    def parse_channel(self, data: dict[str, Any]) -> SlackChannel:
        """
        Slack API 채널 응답 → SlackChannel 스키마
        """
        channel_id = data.get("id", "")
        name = data.get("name", channel_id)

        # 채널 타입 결정
        if data.get("is_im"):
            channel_type = "dm"
        elif data.get("is_mpim"):
            channel_type = "mpim"
        elif data.get("is_private"):
            channel_type = "private"
        else:
            channel_type = "public"

        # Topic & Purpose
        topic = data.get("topic", {}).get("value")
        purpose = data.get("purpose", {}).get("value")

        # 시간 변환
        created_ts = data.get("created", 0)
        created_at = datetime.fromtimestamp(created_ts, tz=timezone.utc) if created_ts else datetime.now(timezone.utc)

        return SlackChannel(
            id=channel_id,
            name=name,
            channel_type=channel_type,
            topic=topic,
            purpose=purpose,
            creator_id=data.get("creator"),
            member_count=data.get("num_members", 0),
            member_ids=[],  # conversations_members로 별도 조회 필요
            is_archived=data.get("is_archived", False),
            is_private=data.get("is_private", False),
            is_mpim=data.get("is_mpim", False),
            is_im=data.get("is_im", False),
            created_at=created_at,
            updated_at=None,
        )

    def parse_user(self, data: dict[str, Any]) -> SlackUserProfile:
        """
        Slack API 사용자 응답 → SlackUserProfile 스키마
        """
        profile = data.get("profile", {})

        # 시간 변환
        updated_ts = data.get("updated", 0)
        updated_at = datetime.fromtimestamp(updated_ts, tz=timezone.utc) if updated_ts else None

        return SlackUserProfile(
            id=data.get("id", ""),
            team_id=data.get("team_id"),
            name=data.get("name", ""),
            real_name=profile.get("real_name") or data.get("real_name"),
            display_name=profile.get("display_name"),
            email=profile.get("email"),
            title=profile.get("title"),
            phone=profile.get("phone"),
            status_text=profile.get("status_text"),
            status_emoji=profile.get("status_emoji"),
            tz=data.get("tz"),
            tz_label=data.get("tz_label"),
            is_bot=data.get("is_bot", False),
            is_admin=data.get("is_admin", False),
            is_owner=data.get("is_owner", False),
            is_primary_owner=data.get("is_primary_owner", False),
            is_restricted=data.get("is_restricted", False),
            is_ultra_restricted=data.get("is_ultra_restricted", False),
            deleted=data.get("deleted", False),
            avatar_url=profile.get("image_512") or profile.get("image_192"),
            custom_fields=profile.get("fields", {}),
            updated_at=updated_at,
        )

    def parse_file(self, data: dict[str, Any]) -> SlackFile:
        """
        Slack API 파일 응답 → SlackFile 스키마
        """
        # 작성자 정보
        user_id = data.get("user")
        user_info = self.user_cache.get(user_id) if user_id else None

        # 시간 변환
        created_ts = data.get("created", 0)
        created_at = datetime.fromtimestamp(created_ts, tz=timezone.utc) if created_ts else datetime.now(timezone.utc)

        return SlackFile(
            id=data.get("id", ""),
            name=data.get("name", ""),
            title=data.get("title"),
            filetype=data.get("filetype", ""),
            mimetype=data.get("mimetype"),
            pretty_type=data.get("pretty_type"),
            size=data.get("size", 0),
            user_id=user_id,
            user_name=user_info.name if user_info else None,
            channel_ids=data.get("channels", []),
            url_private=data.get("url_private"),
            url_private_download=data.get("url_private_download"),
            permalink=data.get("permalink"),
            initial_comment=data.get("initial_comment", {}).get("comment"),
            mode=data.get("mode"),
            is_external=data.get("is_external", False),
            external_type=data.get("external_type"),
            created_at=created_at,
        )

    def parse_workspace(self, data: dict[str, Any]) -> SlackWorkspace:
        """
        Slack API Team 응답 → SlackWorkspace 스키마
        """
        team = data.get("team", data)  # team.info 응답 구조

        return SlackWorkspace(
            id=team.get("id", ""),
            name=team.get("name", ""),
            domain=team.get("domain", ""),
            url=f"https://{team.get('domain', '')}.slack.com/",
            email_domain=team.get("email_domain"),
            icon_url=team.get("icon", {}).get("image_132"),
            enterprise_id=team.get("enterprise_id"),
            enterprise_name=team.get("enterprise_name"),
        )

    # ================================================================
    # 유틸리티 메서드
    # ================================================================

    def _parse_slack_markdown(self, text: str) -> str:
        """
        Slack 마크다운 → 평문 변환

        - <@U123> → @username (user_cache 사용)
        - <#C123|channel> → #channel
        - <url|text> → text
        - &amp; → &, &lt; → <, &gt; → >
        """
        if not text:
            return ""

        result = text

        # 사용자 멘션: <@U123> → @username
        def replace_user_mention(match: re.Match) -> str:
            user_id = match.group(1)
            user = self.user_cache.get(user_id)
            if user:
                return f"@{user.name or user.real_name or user_id}"
            return f"@{user_id}"

        result = re.sub(r"<@([A-Z0-9]+)>", replace_user_mention, result)

        # 채널 링크: <#C123|channel> → #channel
        result = re.sub(r"<#[A-Z0-9]+\|([^>]+)>", r"#\1", result)
        result = re.sub(r"<#([A-Z0-9]+)>", r"#\1", result)

        # 날짜 포맷팅: <!date^timestamp^format|fallback> → 날짜 문자열
        def replace_date_format(match: re.Match) -> str:
            timestamp_str = match.group(1)
            # fallback이 있는 경우 group(2), 없으면 빈 문자열
            fallback = match.group(2) if len(match.groups()) > 1 and match.group(2) else ""
            try:
                timestamp = int(timestamp_str)
                dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                # 한국 시간대 변환 (UTC+9)
                dt_kst = dt + timedelta(hours=9)
                return dt_kst.strftime("%Y-%m-%d %H:%M")
            except (ValueError, OSError):
                return fallback.strip() if fallback else timestamp_str

        # <!date^1770011104^{format}|fallback> 패턴 (fallback 있는 경우)
        result = re.sub(
            r"<!date\^(\d+)\^[^|>]*\|([^>]*)>",
            replace_date_format,
            result
        )
        # <!date^timestamp^format> (fallback 없는 경우)
        def replace_date_no_fallback(match: re.Match) -> str:
            timestamp_str = match.group(1)
            try:
                timestamp = int(timestamp_str)
                dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                dt_kst = dt + timedelta(hours=9)
                return dt_kst.strftime("%Y-%m-%d %H:%M")
            except (ValueError, OSError):
                return timestamp_str

        result = re.sub(
            r"<!date\^(\d+)\^[^>]*>",
            replace_date_no_fallback,
            result
        )

        # URL 링크: <url|text> → text
        result = re.sub(r"<([^|>]+)\|([^>]+)>", r"\2", result)
        # 단순 URL: <url> → url
        result = re.sub(r"<([^>]+)>", r"\1", result)

        # HTML 엔티티 디코딩
        result = result.replace("&amp;", "&")
        result = result.replace("&lt;", "<")
        result = result.replace("&gt;", ">")

        return result

    def _extract_mentioned_users(self, text: str) -> list[SlackUser]:
        """
        텍스트에서 멘션된 사용자 추출

        Args:
            text: Slack 메시지 텍스트 (예: "<@U123> 확인 부탁")

        Returns:
            멘션된 SlackUser 목록 (중복 제거)
        """
        if not text:
            return []

        mentioned_users = []
        seen_ids = set()

        # <@U123> 패턴 찾기
        pattern = r"<@([A-Z0-9]+)>"
        for match in re.finditer(pattern, text):
            user_id = match.group(1)
            if user_id not in seen_ids:
                seen_ids.add(user_id)
                user = self.user_cache.get(user_id)
                if user:
                    mentioned_users.append(user)
                else:
                    mentioned_users.append(SlackUser(id=user_id))

        return mentioned_users

    def _extract_external_refs(
        self,
        text: str,
    ) -> tuple[list[str], list[str], list[str]]:
        """
        텍스트에서 Jira/GitHub 참조 추출

        Returns:
            (jira_issues, github_prs, github_issues)
        """
        if not text:
            return [], [], []

        # Jira 이슈: CAT-123, PROJ-456
        jira_pattern = r'\b([A-Z]{2,10}-\d+)\b'
        jira_issues = list(set(re.findall(jira_pattern, text)))

        # GitHub PR: owner/repo#123 또는 #123
        # GitHub Issue: owner/repo#123 또는 #123
        # 현재는 구분 불가, 둘 다 github_issues로 처리
        github_pattern = r'(?:([a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+))?#(\d+)'
        github_matches = re.findall(github_pattern, text)
        github_issues = list(set([
            f"{m[0]}#{m[1]}" if m[0] else f"#{m[1]}"
            for m in github_matches
        ]))

        return jira_issues, [], github_issues

    def _ts_to_datetime(self, ts: str | None) -> datetime:
        """Slack timestamp → datetime 변환"""
        if not ts:
            return datetime.now(timezone.utc)
        try:
            epoch = float(ts.split(".")[0])
            return datetime.fromtimestamp(epoch, tz=timezone.utc)
        except (ValueError, IndexError):
            return datetime.now(timezone.utc)
