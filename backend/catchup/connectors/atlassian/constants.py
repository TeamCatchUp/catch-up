from enum import StrEnum

class AtlassianProduct(StrEnum):
    JIRA = "jira"
    CONFLUENCE = "confluence"

REQUIRED_JIRA_SCOPES: set[str] = {
    "read:jira-work"
}

REQUIRED_CONFLUENCE_SCOPES: set[str] = {
    "read:confluence-content.all",
    "read:confluence-space.summary",
    "read:confluence-user",
    "read:space:confluence",
    "read:space.permission:confluence",
    "read:page:confluence",
    "read:blogpost:confluence",
    "read:comment:confluence",
    "read:attachment:confluence",
}