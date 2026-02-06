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

import re
from datetime import datetime
from typing import Any

from langchain_core.documents import Document

from catchup.components.connectors.jira.field_mapper import JiraFieldMapper
from catchup.components.connectors.jira.schemas import (
    JiraAttachment,
    JiraComment,
    JiraComponent,
    JiraEpic,
    JiraIssue,
    JiraLinkedIssue,
    JiraProject,
    JiraSprint,
    JiraSprintInfo,
    JiraStatusChange,
    JiraUser,
)
from catchup.configs.config import settings


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
    """

    def __init__(self, field_mapper: JiraFieldMapper):
        self.field_mapper = field_mapper

    # ================================================================
    # Issue 변환
    # ================================================================

    def transform_issue(
        self,
        issue_data: dict[str, Any],
        site_url: str,
        comments: list[dict] | None = None,
        changelog: list[dict] | None = None,
    ) -> Document:
        """
        Jira Issue API 응답 → LangChain Document

        Args:
            issue_data: GET /issue/{key} 응답
            site_url: Jira 사이트 URL (예: "https://catchup.atlassian.net")
            comments: 코멘트 목록 (별도 조회한 경우)
            changelog: 변경 이력 (expand=changelog로 조회한 경우)

        Returns:
            LangChain Document with page_content and metadata
        """
        issue = self._parse_issue(issue_data, site_url, comments, changelog)

        # Epic인 경우 별도 처리
        if issue.issue_type.lower() == "epic":
            return self._issue_to_epic_document(issue)

        return self._issue_to_document(issue)

    def _parse_issue(
        self,
        data: dict[str, Any],
        site_url: str,
        comments: list[dict] | None = None,
        changelog: list[dict] | None = None,
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
        priority = fields.get("priority", {}).get("name") if fields.get("priority") else None
        resolution = fields.get("resolution", {}).get("name") if fields.get("resolution") else None

        # 담당자
        assignee = self._parse_user(fields.get("assignee"))
        reporter = self._parse_user(fields.get("reporter"))
        creator = self._parse_user(fields.get("creator"))

        # 시간
        created_at = self._parse_datetime(fields.get("created"))
        updated_at = self._parse_datetime(fields.get("updated"))
        resolved_at = self._parse_datetime(fields.get("resolutiondate"))
        due_date = fields.get("duedate")  # "2024-02-10" 형식

        # 계층 구조
        parent = fields.get("parent", {})
        parent_key = parent.get("key") if parent else None

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

        # 커스텀 필드 파싱 (Epic Link, Sprint, Story Points 등)
        custom_fields = {}
        epic_key = None
        epic_name = None
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

            # Epic Link 처리
            if "epic" in field_name_lower and "link" in field_name_lower:
                epic_key = value if isinstance(value, str) else None
            # Epic Name 처리 (Epic 이슈 타입에서)
            elif "epic" in field_name_lower and "name" in field_name_lower:
                epic_name = value if isinstance(value, str) else None
            # Sprint 처리
            elif field_name_lower == "sprint":
                sprint_info = self._parse_sprint_field(value)
            # Story Points 처리
            elif "story" in field_name_lower and "point" in field_name_lower:
                story_points = float(value) if value else None
            # Parent Link (next-gen projects)
            elif "parent" in field_name_lower and "link" in field_name_lower:
                if not epic_key and isinstance(value, str):
                    epic_key = value
            else:
                # 기타 커스텀 필드 저장
                custom_fields[field_name] = value

        # 코멘트 파싱
        parsed_comments = []
        if comments:
            parsed_comments = self._parse_comments(comments)
        elif fields.get("comment", {}).get("comments"):
            parsed_comments = self._parse_comments(fields["comment"]["comments"])

        # 상태 변경 이력 파싱
        status_changes = []
        if changelog:
            status_changes = self._parse_status_changes(changelog)

        return JiraIssue(
            key=key,
            id=issue_id,
            url=url,
            project_key=project_key,
            project_name=project_name,
            issue_type=issue_type,
            status=status,
            priority=priority,
            resolution=resolution,
            summary=fields.get("summary", ""),
            description=self._extract_text(fields.get("description")),
            assignee=assignee,
            reporter=reporter,
            creator=creator,
            created_at=created_at,
            updated_at=updated_at,
            resolved_at=resolved_at,
            due_date=due_date,
            parent_key=parent_key,
            epic_key=epic_key,
            epic_name=epic_name,
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
            status_changes=status_changes,
            attachments=attachments,
            custom_fields=custom_fields,
        )

    def _issue_to_document(self, issue: JiraIssue) -> Document:
        """JiraIssue → LangChain Document"""

        # page_content 생성
        page_content = self._build_issue_content(issue)

        # metadata 생성
        metadata = {
            # 기본 식별
            "source": "jira",
            "entity_type": "issue",
            "issue_key": issue.key,
            "issue_id": issue.id,
            "url": issue.url,

            # 분류
            "project_key": issue.project_key,
            "project_name": issue.project_name,
            "issue_type": issue.issue_type,
            "status": issue.status,
            "priority": issue.priority,
            "resolution": issue.resolution,

            # 담당자
            "assignee": issue.assignee.display_name if issue.assignee else None,
            "assignee_email": issue.assignee.email_address if issue.assignee else None,
            "reporter": issue.reporter.display_name if issue.reporter else None,

            # 시간
            "created_at": issue.created_at.isoformat() if issue.created_at else None,
            "updated_at": issue.updated_at.isoformat() if issue.updated_at else None,
            "resolved_at": issue.resolved_at.isoformat() if issue.resolved_at else None,
            "due_date": issue.due_date,

            # 계층
            "parent_key": issue.parent_key,
            "epic_key": issue.epic_key,
            "epic_name": issue.epic_name,
            "subtask_keys": issue.subtask_keys,

            # Agile
            "sprint_name": issue.sprint.name if issue.sprint else None,
            "sprint_state": issue.sprint.state if issue.sprint else None,
            "story_points": issue.story_points,

            # 분류 태그
            "components": issue.components,
            "labels": issue.labels,
            "fix_versions": issue.fix_versions,

            # 시간 추적
            "time_spent_seconds": issue.time_spent_seconds,

            # 동기화
            "synced_at": datetime.utcnow().isoformat(),
        }

        return Document(
            page_content=page_content,
            metadata=metadata,
            id=f"jira:issue:{issue.key}",
        )

    def _build_issue_content(self, issue: JiraIssue) -> str:
        """Issue용 page_content 생성"""
        lines = [
            f"[{issue.key}] {issue.summary}",
            "",
            f"Status: {issue.status} | Priority: {issue.priority or 'None'} | Type: {issue.issue_type}",
            f"Assigned to: {issue.assignee.display_name if issue.assignee else 'Unassigned'} | Reporter: {issue.reporter.display_name if issue.reporter else 'Unknown'}",
            f"Epic: {issue.epic_name or 'None'} | Sprint: {issue.sprint.name if issue.sprint else 'No sprint'}",
        ]

        # Description
        if issue.description:
            lines.extend(["", "Description:", issue.description])

        # Recent Comments (최근 5개)
        if issue.comments:
            lines.extend(["", "Recent Discussion:"])
            for comment in issue.comments[-settings.JIRA_SYNC_COMMENTS_LIMIT:]:
                date_str = comment.created.strftime("%Y-%m-%d %H:%M")
                lines.append(f"[{date_str} {comment.author}]: {comment.body[:200]}")

        # Technical Context
        lines.extend(["", "Technical Context:"])
        lines.append(f"- Components: {', '.join(issue.components) or 'None'}")
        lines.append(f"- Labels: {', '.join(issue.labels) or 'None'}")
        lines.append(f"- Fix Version: {', '.join(issue.fix_versions) or 'None'}")

        # Status History
        if issue.status_changes:
            lines.extend(["", "Status History:"])
            for change in issue.status_changes[-5:]:
                date_str = change.changed_at.strftime("%Y-%m-%d %H:%M")
                lines.append(
                    f"{change.from_status or 'Created'} → {change.to_status} "
                    f"({date_str} by {change.author or 'Unknown'})"
                )

        # Related Issues
        if issue.linked_issues:
            lines.extend(["", "Related Issues:"])
            for link in issue.linked_issues[:5]:
                lines.append(
                    f"- {link.key} ({link.summary or 'No summary'}) - "
                    f"{link.status or 'Unknown'} - {link.link_type}"
                )

        return "\n".join(lines)

    # ================================================================
    # Epic 변환
    # ================================================================

    def _issue_to_epic_document(self, issue: JiraIssue) -> Document:
        """Epic Issue → LangChain Document (별도 entity_type)"""

        # Epic용 page_content
        lines = [
            f"[Epic: {issue.key}] {issue.summary}",
            "",
            f"Status: {issue.status} | Priority: {issue.priority or 'None'}",
            f"Owner: {issue.assignee.display_name if issue.assignee else 'Unassigned'}",
        ]

        if issue.description:
            lines.extend(["", "Epic Description:", issue.description])

        lines.extend(["", "Technical Context:"])
        lines.append(f"- Components: {', '.join(issue.components) or 'None'}")
        lines.append(f"- Labels: {', '.join(issue.labels) or 'None'}")
        lines.append(f"- Target Version: {', '.join(issue.fix_versions) or 'None'}")

        page_content = "\n".join(lines)

        # Epic metadata
        metadata = {
            "source": "jira",
            "entity_type": "epic",
            "issue_key": issue.key,
            "issue_id": issue.id,
            "url": issue.url,
            "epic_name": issue.epic_name or issue.summary,
            "project_key": issue.project_key,
            "project_name": issue.project_name,
            "status": issue.status,
            "priority": issue.priority,
            "assignee": issue.assignee.display_name if issue.assignee else None,
            "created_at": issue.created_at.isoformat() if issue.created_at else None,
            "updated_at": issue.updated_at.isoformat() if issue.updated_at else None,
            "components": issue.components,
            "labels": issue.labels,
            "fix_versions": issue.fix_versions,
            "synced_at": datetime.utcnow().isoformat(),
        }

        return Document(
            page_content=page_content,
            metadata=metadata,
            id=f"jira:epic:{issue.key}",
        )

    # ================================================================
    # Project 변환
    # ================================================================

    def transform_project(
        self,
        project_data: dict[str, Any],
        site_url: str,
    ) -> Document:
        """Jira Project → LangChain Document"""

        key = project_data.get("key", "")
        project_id = project_data.get("id", "")
        name = project_data.get("name", "")
        url = f"{site_url}/projects/{key}"

        description = project_data.get("description", "")
        project_type = project_data.get("projectTypeKey", "")

        lead = self._parse_user(project_data.get("lead"))

        components = [c.get("name") for c in project_data.get("components", []) if c.get("name")]
        versions = [v.get("name") for v in project_data.get("versions", []) if v.get("name")]

        # page_content
        lines = [
            f"Project: {name} [{key}]",
            "",
            f"Description:",
            description or "No description",
            "",
            f"Project Lead: {lead.display_name if lead else 'Unknown'}",
            f"Project Type: {project_type}",
            "",
            f"Components: {', '.join(components) or 'None'}",
            f"Versions: {', '.join(versions) or 'None'}",
        ]

        page_content = "\n".join(lines)

        metadata = {
            "source": "jira",
            "entity_type": "project",
            "project_key": key,
            "project_id": project_id,
            "project_name": name,
            "url": url,
            "project_type": project_type,
            "project_lead": lead.display_name if lead else None,
            "components": components,
            "versions": versions,
            "synced_at": datetime.utcnow().isoformat(),
        }

        return Document(
            page_content=page_content,
            metadata=metadata,
            id=f"jira:project:{key}",
        )

    # ================================================================
    # Sprint 변환
    # ================================================================

    def transform_sprint(
        self,
        sprint_data: dict[str, Any],
        project_key: str | None = None,
    ) -> Document:
        """Jira Sprint (Agile API) → LangChain Document"""

        sprint_id = sprint_data.get("id")
        name = sprint_data.get("name", "")
        state = sprint_data.get("state", "")
        goal = sprint_data.get("goal", "")

        start_date = sprint_data.get("startDate")
        end_date = sprint_data.get("endDate")
        complete_date = sprint_data.get("completeDate")

        # page_content
        lines = [
            f"Sprint: {name} (ID: {sprint_id})",
            "",
            f"Status: {state}",
            f"Start: {start_date or 'Not started'} | End: {end_date or 'Not set'}",
        ]

        if goal:
            lines.extend(["", f"Goal: {goal}"])

        page_content = "\n".join(lines)

        metadata = {
            "source": "jira",
            "entity_type": "sprint",
            "sprint_id": sprint_id,
            "sprint_name": name,
            "sprint_state": state,
            "sprint_goal": goal,
            "project_key": project_key,
            "start_date": start_date,
            "end_date": end_date,
            "complete_date": complete_date,
            "synced_at": datetime.utcnow().isoformat(),
        }

        return Document(
            page_content=page_content,
            metadata=metadata,
            id=f"jira:sprint:{sprint_id}",
        )

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
        )

    def _parse_datetime(self, dt_str: str | None) -> datetime | None:
        """ISO 날짜 문자열 → datetime"""
        if not dt_str:
            return None
        try:
            # "2024-02-01T09:00:00.000+0900" 형식
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _parse_comments(self, comments_data: list[dict]) -> list[JiraComment]:
        """코멘트 목록 파싱"""
        result = []
        for c in comments_data:
            author = c.get("author", {}).get("displayName", "Unknown")
            body = self._extract_text(c.get("body"))
            created = self._parse_datetime(c.get("created"))
            if created:
                result.append(JiraComment(
                    id=c.get("id", ""),
                    author=author,
                    body=body,
                    created=created,
                ))
        return result

    def _parse_status_changes(self, changelog: list[dict]) -> list[JiraStatusChange]:
        """상태 변경 이력 파싱 (changelog에서 status 변경만 추출)"""
        result = []
        for entry in changelog:
            author = entry.get("author", {}).get("displayName")
            created = self._parse_datetime(entry.get("created"))

            for item in entry.get("items", []):
                if item.get("field") == "status":
                    result.append(JiraStatusChange(
                        from_status=item.get("fromString"),
                        to_status=item.get("toString"),
                        changed_at=created,
                        author=author,
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
                summary=issue.get("fields", {}).get("summary"),
                status=issue.get("fields", {}).get("status", {}).get("name"),
                link_type=link_type_name,
            ))
        return result

    def _parse_attachments(self, attachments_data: list[dict]) -> list[JiraAttachment]:
        """첨부파일 파싱"""
        result = []
        for att in attachments_data:
            result.append(JiraAttachment(
                filename=att.get("filename", ""),
                author=att.get("author", {}).get("displayName"),
                mime_type=att.get("mimeType"),
                url=att.get("content"),
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

    def _extract_text(self, content: Any) -> str:
        """
        Jira ADF (Atlassian Document Format) → 평문 텍스트

        Jira Cloud는 description, comment 등을 ADF JSON으로 반환.
        이를 평문 텍스트로 변환.
        """
        if not content:
            return ""

        if isinstance(content, str):
            return content

        if not isinstance(content, dict):
            return str(content)

        # ADF 형식
        if content.get("type") == "doc":
            return self._adf_to_text(content)

        return str(content)

    def _adf_to_text(self, adf: dict) -> str:
        """ADF JSON → 평문 텍스트 변환"""
        texts = []

        def extract(node: Any):
            if isinstance(node, dict):
                if node.get("type") == "text":
                    texts.append(node.get("text", ""))
                elif node.get("type") == "hardBreak":
                    texts.append("\n")
                elif node.get("type") == "paragraph":
                    for child in node.get("content", []):
                        extract(child)
                    texts.append("\n")
                else:
                    for child in node.get("content", []):
                        extract(child)
            elif isinstance(node, list):
                for item in node:
                    extract(item)

        extract(adf.get("content", []))
        return "".join(texts).strip()
