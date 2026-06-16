"""
Jira 엔티티 → LangChain Document 변환기

Jira API 응답을 Pydantic Schema로 파싱하고,
PGVector 저장을 위한 LangChain Document로 변환.

변환 흐름:
    1. Jira API 응답 (dict) → Pydantic Schema (JiraIssue, JiraEpic 등)
    2. Pydantic Schema → LangChain Document (page_content + metadata)

사용법:
    transformer = JiraTransformer(field_mapper)

    # API 응답 → Document
    issue_data = await client.get_issue("CATCH-145")
    doc = transformer.transform_issue(issue_data, site_url)
"""

from datetime import datetime
from typing import Any

from langchain_core.documents import Document

from catchup.connectors.atlassian.adf_parser import extract_media
from catchup.connectors.atlassian.adf_parser import extract_mentions
from catchup.connectors.atlassian.adf_parser import extract_text
from catchup.connectors.atlassian.utils import parse_atlassian_datetime
from catchup.connectors.jira.field_mapper import JiraFieldMapper
from catchup.connectors.jira.schemas import JiraAttachment
from catchup.connectors.jira.schemas import JiraComment
from catchup.connectors.jira.schemas import JiraInlineAttachment
from catchup.connectors.jira.schemas import JiraIssue
from catchup.connectors.jira.schemas import JiraLinkedIssue
from catchup.connectors.jira.schemas import JiraMention
from catchup.connectors.jira.schemas import JiraSprintInfo
from catchup.connectors.jira.schemas import JiraUser
from catchup.sync.ingestion.document_format import DocumentBaseMetadata
from catchup.sync.ingestion.document_format import JiraAttachmentMetadata
from catchup.sync.ingestion.document_format import JiraIssueLogicalMetadata
from catchup.sync.ingestion.document_format import JiraIssueMetadata

# ============================================================
# Jira 인스턴스 언어 설정에 관계없이 영어로 통일
# ============================================================
ISSUE_TYPE_MAPPING: dict[str, str] = {
    # 한국어
    "에픽": "Epic",
    "스토리": "Story",
    "작업": "Task",
    "하위 작업": "Sub-task",
    "버그": "Bug",
    "개선": "Improvement",
    "새 기능": "New Feature",
}


def normalize_issue_type(issue_type: str) -> str:
    """이슈 타입을 영어로 정규화"""
    return ISSUE_TYPE_MAPPING.get(issue_type, issue_type)


class JiraTransformer:
    """
    Jira 엔티티 → LangChain Document 변환기

    Attributes:
        field_mapper: 커스텀 필드 ID → 이름 변환용 매퍼
        project_cache: RDBMS에서 로드한 프로젝트 정보 캐시 (project_key → JiraProject)
        sprint_cache: RDBMS에서 로드한 스프린트 정보 캐시 (sprint_id → JiraSprint)
    """

    def __init__(self, field_mapper: JiraFieldMapper):
        self.field_mapper = field_mapper
        # RDBMS 캐시 (service에서 주입)
        self.project_cache: dict[str, Any] = {}
        self.sprint_cache: dict[int, Any] = {}

    # ================================================================
    # Issue 변환
    # ================================================================

    def transform_issue(
        self,
        issue_data: dict[str, Any],
        site_url: str,
        comments: list[dict] | None = None,
    ) -> Document:
        """
        Jira Issue API 응답 → LangChain Document

        Args:
            issue_data: GET /issue/{key} 응답
            site_url: Jira 사이트 URL (예: "https://catchup.atlassian.net")
            comments: 코멘트 목록 (별도 조회한 경우)

        Returns:
            LangChain Document with page_content and metadata
        """
        issue = self.parse_issue(issue_data, site_url, comments)

        return self._issue_to_document(issue)

    def parse_issue(
        self,
        issue_data: dict[str, Any],
        site_url: str,
        comments: list[dict] | None = None,
    ) -> JiraIssue:
        return self._parse_issue(issue_data, site_url, comments)

    def _parse_issue(
        self,
        data: dict[str, Any],
        site_url: str,
        comments: list[dict] | None = None,
    ) -> JiraIssue:
        """Jira API 응답 → JiraIssue 스키마"""
        fields = data.get("fields", {})

        # 기본 정보
        key = data["key"]
        issue_id = data["id"]
        url = f"{site_url}/browse/{key}"

        # 프로젝트
        project = fields.get("project", {})
        project_key = project.get("key", "")
        project_name = project.get("name", "")

        # 타입, 상태, 우선순위 (이슈 타입은 영어로 정규화)
        issue_type_raw = fields.get("issuetype", {}).get("name", "")
        issue_type = normalize_issue_type(issue_type_raw)
        status = fields.get("status", {}).get("name", "")
        status_category = (
            fields.get("status", {}).get("statusCategory", {}).get("name")
            if fields.get("status")
            else None
        )
        priority = fields.get("priority", {}).get("name") if fields.get("priority") else None
        resolution = fields.get("resolution", {}).get("name") if fields.get("resolution") else None

        # 담당자
        assignee = self._parse_user(fields.get("assignee"))
        reporter = self._parse_user(fields.get("reporter"))
        creator = self._parse_user(fields.get("creator"))

        # 시간
        created_at = parse_atlassian_datetime(fields.get("created"))
        updated_at = parse_atlassian_datetime(fields.get("updated"))
        resolved_at = parse_atlassian_datetime(fields.get("resolutiondate"))
        due_date = fields.get("duedate")  # "2024-02-10" 형식

        # 계층 구조
        # 계층 구조 (Parent Issue - Epic, Task 등)
        parent = fields.get("parent", {})
        parent_key = parent.get("key") if parent else None
        parent_name = None
        if parent:
            parent_fields = parent.get("fields", {})
            parent_name = parent_fields.get("summary")

        # Subtasks
        subtasks = fields.get("subtasks", [])
        subtask_keys = [st.get("key") for st in subtasks if st.get("key")]

        # 분류 태그
        components = [c.get("name") for c in fields.get("components", []) if c.get("name")]
        labels = fields.get("labels", [])
        fix_versions = [v.get("name") for v in fields.get("fixVersions", []) if v.get("name")]
        affects_versions = [v.get("name") for v in fields.get("versions", []) if v.get("name")]

        # 시간 추적
        time_spent = fields.get("timespent")  # 초 단위

        # 연결된 이슈
        linked_issues = self._parse_linked_issues(fields.get("issuelinks", []))

        # 첨부파일
        attachments = self._parse_attachments(fields.get("attachment", []))

        # 커스텀 필드 파싱 (Sprint, Story Points 등)
        custom_fields = {}
        sprint_info = None
        story_points = None

        for field_id, value in fields.items():
            if not field_id.startswith("customfield_") or value is None:
                continue

            field_info = self.field_mapper.get_field_info_by_id(field_id)
            if not field_info:
                continue

            field_name = field_info.name
            field_name_lower = field_name.lower()

            # Sprint 처리
            if field_name_lower == "sprint":
                sprint_info = self._parse_sprint_field(value)
            # Story Points 처리
            elif "story" in field_name_lower and "point" in field_name_lower:
                story_points = float(value) if value else None
            else:
                # 기타 커스텀 필드 저장
                custom_fields[field_name] = value

        # 코멘트 파싱
        parsed_comments = []
        if comments:
            parsed_comments = self._parse_comments(comments, site_url)
        elif fields.get("comment", {}).get("comments"):
            parsed_comments = self._parse_comments(fields["comment"]["comments"], site_url)

        return JiraIssue(
            key=key,
            id=issue_id,
            url=url,
            project_key=project_key,
            project_name=project_name,
            issue_type=issue_type,
            status=status,
            status_category=status_category,
            priority=priority,
            resolution=resolution,
            summary=fields.get("summary", ""),
            description=extract_text(fields.get("description")),
            assignee=assignee,
            reporter=reporter,
            creator=creator,
            created_at=created_at,
            updated_at=updated_at,
            resolved_at=resolved_at,
            due_date=due_date,
            parent_key=parent_key,
            parent_name=parent_name,
            subtask_keys=subtask_keys,
            sprint=sprint_info,
            story_points=story_points,
            components=components,
            labels=labels,
            fix_versions=fix_versions,
            affects_versions=affects_versions,
            time_spent_seconds=time_spent,
            linked_issues=linked_issues,
            comments=parsed_comments,
            attachments=attachments,
            custom_fields=custom_fields,
        )

    def _issue_to_document(self, issue: JiraIssue) -> Document:
        """JiraIssue → LangChain Document"""

        # semantic_content: 임베딩용 (의미 중심 텍스트)
        semantic_content = self._build_issue_semantic_content(issue)

        # contextual_content: LLM 답변 생성용 (기존 포맷)
        contextual_content = self._build_issue_contextual_content(issue)

        metadata = self._build_issue_storage_metadata(
            issue=issue,
            contextual_content=contextual_content,
        )

        return Document(
            page_content=semantic_content,
            metadata=metadata,
            id=f"jira:issue:{issue.key}",
        )

    def _build_issue_semantic_content(self, issue: JiraIssue) -> str:
        """
        Issue용 semantic_content 생성 (의미 중심)

        포함: summary, description, comments(본문만)
        제외: 메타데이터(Status, Priority, Type, Assignee 등), 포맷 마커
        """
        parts = []

        # 1. Summary (제목)
        if issue.summary:
            parts.append(issue.summary)

        # 2. Description (설명)
        if issue.description:
            parts.append(issue.description)

        # 3. Comments (본문만, author 제외)
        for comment in issue.comments:
            if comment.body:
                parts.append(comment.body)

        return "\n\n".join(parts)

    def _build_issue_contextual_content(self, issue: JiraIssue) -> str:
        """Issue용 contextual_content 생성 - LLM 답변 생성용 (RDBMS 캐시 활용)"""
        # Parent 정보 포맷팅
        if issue.parent_key and issue.parent_name:
            parent_str = f"{issue.parent_key} ({issue.parent_name})"
        elif issue.parent_key:
            parent_str = issue.parent_key
        else:
            parent_str = "None"

        # Sprint 정보 enrichment (RDBMS 캐시 활용)
        sprint_str = "No sprint"
        if issue.sprint:
            sprint_str = issue.sprint.name
            # 캐시에서 추가 정보 조회
            if issue.sprint.id and issue.sprint.id in self.sprint_cache:
                cached_sprint = self.sprint_cache[issue.sprint.id]
                state = getattr(cached_sprint, 'state', None)
                goal = getattr(cached_sprint, 'goal', None)
                if state:
                    sprint_str = f"{issue.sprint.name} ({state})"
                if goal:
                    sprint_str += f" - Goal: {goal[:80]}{'...' if len(goal) > 80 else ''}"

        lines = [
            f"[{issue.key}] {issue.summary}",
            "",
            f"Status: {issue.status} | Priority: {issue.priority or 'None'} | Type: {issue.issue_type}",
            f"Assigned to: {issue.assignee.display_name if issue.assignee else 'Unassigned'} | Reporter: {issue.reporter.display_name if issue.reporter else 'Unknown'}",
            f"Parent: {parent_str} | Sprint: {sprint_str}",
        ]

        # Description
        if issue.description:
            lines.extend(["", "Description:", issue.description])

        # Comments (모든 코멘트 포함)
        if issue.comments:
            lines.extend(["", "Discussion:"])
            for comment in issue.comments:
                date_str = comment.created.strftime("%Y-%m-%d %H:%M")
                # 코멘트 본문 (길이 제한 없이 전체 포함)
                comment_line = f"[{date_str} {comment.author}]: {comment.body}"

                # 멘션이 있으면 표시
                if comment.mentions:
                    mention_names = [m.display_name or m.account_id for m in comment.mentions]
                    comment_line += f" (mentions: {', '.join(mention_names)})"

                # 인라인 첨부파일이 있으면 파일명 표시
                if comment.inline_attachments:
                    filenames = [
                        att.filename or att.alt or f"media:{att.id[:8]}"
                        for att in comment.inline_attachments
                    ]
                    comment_line += f" [attachments: {', '.join(filenames)}]"

                lines.append(comment_line)

        # Technical Context (내용이 있을 때만 표시)
        tech_context_items = []
        if issue.components:
            tech_context_items.append(f"- Components: {', '.join(issue.components)}")
        if issue.labels:
            tech_context_items.append(f"- Labels: {', '.join(issue.labels)}")
        if issue.fix_versions:
            tech_context_items.append(f"- Fix Version: {', '.join(issue.fix_versions)}")

        if tech_context_items:
            lines.extend(["", "Technical Context:"])
            lines.extend(tech_context_items)

        # Related Issues
        if issue.linked_issues:
            lines.extend(["", "Related Issues:"])
            for link in issue.linked_issues[:5]:
                lines.append(
                    f"- {link.key} ({link.summary or 'No summary'}) - "
                    f"{link.status or 'Unknown'} - {link.link_type}"
                )

        # Attachments (파일명만 표시)
        if issue.attachments:
            lines.extend(["", "Attachments:"])
            for att in issue.attachments:
                lines.append(f"- {att.filename}")

        return "\n".join(lines)

    def _build_issue_storage_metadata(
        self,
        *,
        issue: JiraIssue,
        contextual_content: str,
    ) -> dict[str, object]:
        synced_at = datetime.utcnow()
        logical_metadata = JiraIssueLogicalMetadata(
            base=DocumentBaseMetadata(
                source="jira",
                record_id=issue.key,
                url=issue.url,
                created_at=issue.created_at,
                updated_at=issue.updated_at,
                synced_at=synced_at,
                contextual_content=contextual_content,
            ),
            issue=JiraIssueMetadata(
                entity_type="issue",
                issue_key=issue.key,
                issue_id=issue.id,
                title=issue.summary,
                project_key=issue.project_key,
                issue_type=issue.issue_type,
                status=issue.status,
                priority=issue.priority,
                assignee=issue.assignee.display_name if issue.assignee else None,
                assignee_email=issue.assignee.email_address
                if issue.assignee
                else None,
                reporter=issue.reporter.display_name if issue.reporter else None,
                resolved_at=issue.resolved_at,
                parent_key=issue.parent_key,
                subtask_keys=tuple(issue.subtask_keys),
                sprint_id=issue.sprint.id if issue.sprint else None,
                sprint_name=issue.sprint.name if issue.sprint else None,
                components=tuple(issue.components),
                labels=tuple(issue.labels),
                fix_versions=tuple(issue.fix_versions),
                inline_attachments=tuple(
                    JiraAttachmentMetadata(
                        filename=att.filename or att.alt or f"media:{att.id[:8]}",
                        url=att.url,
                        type=att.type,
                    )
                    for comment in issue.comments
                    for att in comment.inline_attachments
                ),
                attachments=tuple(
                    JiraAttachmentMetadata(
                        filename=att.filename,
                        url=att.url,
                        mime_type=att.mime_type,
                    )
                    for att in issue.attachments
                ),
            ),
        )
        return logical_metadata.to_storage_metadata()

    # ================================================================
    # 헬퍼 메서드
    # ================================================================

    def _parse_user(self, user_data: dict | None) -> JiraUser | None:
        """사용자 정보 파싱"""
        if not user_data:
            return None
        return JiraUser(
            account_id=user_data.get("accountId"),
            display_name=user_data.get("displayName"),
            email_address=user_data.get("emailAddress"),
            avatar_url=user_data.get("avatarUrls", {}).get("48x48")
            or user_data.get("avatarUrl"),
            active=user_data.get("active"),
        )

    def _parse_comments(
        self, comments_data: list[dict], site_url: str = ""
    ) -> list[JiraComment]:
        """코멘트 목록 파싱 (멘션 및 인라인 첨부파일 포함)"""
        result = []
        for c in comments_data:
            author = c.get("author", {}).get("displayName", "Unknown")
            author_account_id = c.get("author", {}).get("accountId")
            author_user = self._parse_user(c.get("author"))
            body_adf = c.get("body")
            body = extract_text(body_adf)
            created = parse_atlassian_datetime(c.get("created"))
            updated = parse_atlassian_datetime(c.get("updated"))
            visibility_data = c.get("visibility")
            visibility = None
            if isinstance(visibility_data, dict):
                visibility = visibility_data.get("value") or visibility_data.get("type")

            # ADF에서 멘션 및 인라인 미디어 추출
            mentions: list[JiraMention] = []
            inline_attachments: list[JiraInlineAttachment] = []
            if isinstance(body_adf, dict) and body_adf.get("type") == "doc":
                mentions = [
                    JiraMention(
                        account_id=m.account_id,
                        display_name=m.display_name,
                        text=m.text,
                    )
                    for m in extract_mentions(body_adf)
                ]
                inline_attachments = [
                    JiraInlineAttachment(
                        id=m.id,
                        collection=m.collection,
                        type=m.type,
                        alt=m.alt,
                        filename=m.filename,
                        url=m.url,
                    )
                    for m in extract_media(body_adf, site_url)
                ]

            if created:
                result.append(JiraComment(
                    id=c.get("id", ""),
                    author=author,
                    author_account_id=author_account_id,
                    author_user=author_user,
                    body=body,
                    created=created,
                    updated=updated,
                    visibility=visibility,
                    mentions=mentions,
                    inline_attachments=inline_attachments,
                ))
        return result

    def _parse_linked_issues(self, links_data: list[dict]) -> list[JiraLinkedIssue]:
        """연결된 이슈 파싱"""
        result = []
        for link in links_data:
            link_type = link.get("type", {}).get("name", "")

            # outwardIssue 또는 inwardIssue
            if link.get("outwardIssue"):
                issue = link["outwardIssue"]
                link_type_name = link.get("type", {}).get("outward", link_type)
            elif link.get("inwardIssue"):
                issue = link["inwardIssue"]
                link_type_name = link.get("type", {}).get("inward", link_type)
            else:
                continue

            result.append(JiraLinkedIssue(
                key=issue.get("key", ""),
                id=issue.get("id"),
                summary=issue.get("fields", {}).get("summary"),
                status=issue.get("fields", {}).get("status", {}).get("name"),
                issue_type=normalize_issue_type(
                    issue.get("fields", {}).get("issuetype", {}).get("name", "")
                )
                or None,
                priority=(
                    issue.get("fields", {}).get("priority", {}).get("name")
                    if issue.get("fields", {}).get("priority")
                    else None
                ),
                link_type=link_type_name,
                direction="outward" if link.get("outwardIssue") else "inward",
                url=f"/browse/{issue.get('key', '')}" if issue.get("key") else None,
            ))
        return result

    def _parse_attachments(self, attachments_data: list[dict]) -> list[JiraAttachment]:
        """첨부파일 파싱"""
        result = []
        for att in attachments_data:
            author = self._parse_user(att.get("author"))
            result.append(JiraAttachment(
                id=att.get("id"),
                filename=att.get("filename", ""),
                author=author.display_name if author else None,
                author_account_id=author.account_id if author else None,
                author_user=author,
                mime_type=att.get("mimeType"),
                url=att.get("content"),
                thumbnail_url=att.get("thumbnail"),
                created=parse_atlassian_datetime(att.get("created")),
                size=att.get("size"),
            ))
        return result

    def _parse_sprint_field(self, sprint_data: Any) -> JiraSprintInfo | None:
        """Sprint 커스텀 필드 파싱 (배열 형태)"""
        if not sprint_data:
            return None

        # Sprint 필드는 보통 배열로 옴
        if isinstance(sprint_data, list) and sprint_data:
            sprint = sprint_data[-1]  # 최신 스프린트
            if isinstance(sprint, dict):
                return JiraSprintInfo(
                    id=sprint.get("id", 0),
                    name=sprint.get("name", ""),
                    state=sprint.get("state"),
                )
        elif isinstance(sprint_data, dict):
            return JiraSprintInfo(
                id=sprint_data.get("id", 0),
                name=sprint_data.get("name", ""),
                state=sprint_data.get("state"),
            )
        return None
