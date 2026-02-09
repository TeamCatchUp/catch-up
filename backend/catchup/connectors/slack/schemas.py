"""
Slack 엔티티 Pydantic 스키마

Slack API 응답을 파싱하고, PGVector Document로 변환하기 위한 중간 모델.
Transformer에서 이 스키마들을 사용하여 LangChain Document를 생성.

우선순위:
- P0 (필수): Message, Channel
- P1 (권장): User, File, Workspace
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ============================================================
# 공통 서브 모델
# ============================================================

class SlackUser(BaseModel):
    """메시지 작성자 등 간단한 사용자 정보"""
    id: str
    name: str | None = None
    real_name: str | None = None
    display_name: str | None = None


class SlackReaction(BaseModel):
    """메시지 리액션"""
    name: str                                    # thumbsup, tada, eyes 등
    count: int
    users: list[str] = Field(default_factory=list)


class SlackFileRef(BaseModel):
    """메시지에 첨부된 파일 참조"""
    id: str
    name: str
    title: str | None = None
    filetype: str | None = None
    mimetype: str | None = None
    size: int | None = None
    url_private: str | None = None               # 다운로드 URL
    permalink: str | None = None


class SlackAttachment(BaseModel):
    """
    Slack 메시지 Attachment (Bot 메시지, 링크 미리보기 등)

    Notion, Jira, GitHub 등 외부 앱 메시지에서 링크 정보 포함
    """
    id: int | None = None
    fallback: str | None = None                  # 평문 요약
    title: str | None = None                     # 링크 제목 (예: "연동 가이드")
    title_link: str | None = None                # 링크 URL
    text: str | None = None                      # 본문 텍스트
    pretext: str | None = None                   # 본문 위 텍스트
    author_name: str | None = None
    author_link: str | None = None
    service_name: str | None = None              # 서비스 이름 (예: "Notion")
    from_url: str | None = None                  # 원본 URL
    footer: str | None = None
    color: str | None = None
    fields: list[dict[str, Any]] = Field(default_factory=list)
    actions: list[dict[str, Any]] = Field(default_factory=list)  # 버튼 등


# ============================================================
# Thread Reply (통합 저장용)
# ============================================================

class SlackThreadReply(BaseModel):
    """
    Thread 내 개별 Reply (부모 메시지에 통합 저장)

    - 부모 메시지의 replies 필드에 포함
    - 작성자 정보 함께 저장하여 컨텍스트 보존
    """
    ts: str
    user_id: str
    user_name: str | None = None
    user_real_name: str | None = None
    text: str
    reactions: list[SlackReaction] = Field(default_factory=list)
    files: list[SlackFileRef] = Field(default_factory=list)


# ============================================================
# Message (Thread Parent 포함)
# ============================================================

class SlackMessage(BaseModel):
    """
    Slack 메시지

    - Thread Parent인 경우 replies 필드에 최근 N개 Reply 포함
    - message_type으로 일반 메시지와 Thread Parent 구분
    """
    # 기본 식별
    ts: str                                      # "1707124200.003543"
    channel_id: str
    channel_name: str | None = None
    url: str | None = None                       # permalink

    # 메시지 정보
    message_type: str = "standard"               # standard, thread_parent, file_share
    text: str
    subtype: str | None = None                   # channel_join, file_share, bot_message 등

    # 작성자
    user_id: str | None = None
    user_name: str | None = None
    user_real_name: str | None = None
    bot_id: str | None = None
    bot_name: str | None = None

    # Thread 정보 (Parent인 경우)
    thread_ts: str | None = None                 # 자신의 ts와 동일하면 Thread Parent
    reply_count: int = 0
    reply_users_count: int = 0
    latest_reply_ts: str | None = None
    replies: list[SlackThreadReply] = Field(default_factory=list)  # 통합 저장

    # Reactions & Files & Attachments
    reactions: list[SlackReaction] = Field(default_factory=list)
    files: list[SlackFileRef] = Field(default_factory=list)
    attachments: list[SlackAttachment] = Field(default_factory=list)

    # Mentioned Users (멘션된 사용자)
    mentioned_users: list[SlackUser] = Field(default_factory=list)

    # 시간
    created_at: datetime
    edited_ts: str | None = None

    # 외부 참조 (Jira, GitHub)
    jira_issues: list[str] = Field(default_factory=list)
    github_prs: list[str] = Field(default_factory=list)
    github_issues: list[str] = Field(default_factory=list)


# ============================================================
# Channel
# ============================================================

class SlackChannel(BaseModel):
    """
    Slack 채널

    - channel_type으로 Public, Private, DM, MPIM 구분
    - Bot이 초대된 채널만 조회 가능
    """
    id: str
    name: str
    channel_type: str                            # public, private, dm, mpim
    topic: str | None = None
    purpose: str | None = None
    creator_id: str | None = None
    member_count: int = 0
    member_ids: list[str] = Field(default_factory=list)
    is_archived: bool = False
    is_private: bool = False
    is_mpim: bool = False
    is_im: bool = False
    created_at: datetime
    updated_at: datetime | None = None


# ============================================================
# User (전체 정보)
# ============================================================

class SlackUserProfile(BaseModel):
    """
    Slack 사용자 프로필

    - Workspace 내 사용자의 전체 프로필 정보
    - User 엔티티로 저장되며, 메시지 변환 시 캐시로 사용
    """
    id: str
    team_id: str | None = None
    name: str                                    # username (멘션에 사용)
    real_name: str | None = None
    display_name: str | None = None
    email: str | None = None
    title: str | None = None
    phone: str | None = None
    status_text: str | None = None
    status_emoji: str | None = None
    tz: str | None = None
    tz_label: str | None = None
    is_bot: bool = False
    is_admin: bool = False
    is_owner: bool = False
    is_primary_owner: bool = False
    is_restricted: bool = False                  # Guest user
    is_ultra_restricted: bool = False            # Single-channel guest
    deleted: bool = False
    avatar_url: str | None = None
    custom_fields: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime | None = None


# ============================================================
# File
# ============================================================

class SlackFile(BaseModel):
    """
    Slack 파일

    - OCR 없이 메타데이터만 저장
    - page_content에 파일명, metadata에 다운로드 URL
    """
    id: str
    name: str
    title: str | None = None
    filetype: str                                # pdf, png, docx 등
    mimetype: str | None = None
    pretty_type: str | None = None               # "PDF", "PNG Image" 등
    size: int
    user_id: str | None = None
    user_name: str | None = None
    channel_ids: list[str] = Field(default_factory=list)
    url_private: str | None = None               # 다운로드 URL
    url_private_download: str | None = None      # 직접 다운로드 URL
    permalink: str | None = None                 # Slack 내 파일 페이지 URL
    initial_comment: str | None = None           # 파일 업로드 시 첨부된 코멘트
    mode: str | None = None                      # hosted, external, snippet 등
    is_external: bool = False
    external_type: str | None = None             # google_drive, dropbox 등
    created_at: datetime


# ============================================================
# Workspace
# ============================================================

class SlackWorkspace(BaseModel):
    """
    Slack 워크스페이스

    - Team 정보
    - Workspace 레벨 설정 정보 포함
    """
    id: str
    name: str
    domain: str                                  # {domain}.slack.com
    url: str                                     # https://{domain}.slack.com/
    email_domain: str | None = None
    icon_url: str | None = None
    enterprise_id: str | None = None             # Enterprise Grid인 경우
    enterprise_name: str | None = None


# ============================================================
# OAuth / 인증 관련 스키마
# ============================================================

class SlackTeamInfo(BaseModel):
    id: str = Field(default="", description="Team ID")
    name: str = Field(default="", description="Team Name")


class SlackAuthedUser(BaseModel):
    id: str


class SlackIncomingWebhook(BaseModel):
    channel: str
    channel_id: str
    configuration_url: str
    url: str


class SlackOAuthTokenResponse(BaseModel):
    ok: bool
    access_token: str = Field(description="Bot Access Token (xoxb-)")
    token_type: str = Field(default="bot")
    scope: str = Field(default="", description="Bot Token scopes")
    bot_user_id: str = Field(default="", description="Bot User ID")
    app_id: str = Field(default="")

    team: SlackTeamInfo = Field(default_factory=SlackTeamInfo)
    authed_user: SlackAuthedUser | None = None
    incoming_webhook: SlackIncomingWebhook | None = None
    refresh_token: str | None = None
    expires_in: int | None = None


class SlackWorkspaceInfo(BaseModel):
    team_id: str
    team_name: str
    bot_user_id: str
    scopes: list[str]
    connected_at: datetime


class SlackInstallationStatus(BaseModel):
    installed: bool
    workspaces: list[SlackWorkspaceInfo] = Field(default_factory=list)
