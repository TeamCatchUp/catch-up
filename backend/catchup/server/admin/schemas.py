from typing import List, Optional

from pydantic import BaseModel, EmailStr


class SourceUserCount(BaseModel):
    users: int
    premap: int


class SyncStatusCounts(BaseModel):
    jira: SourceUserCount
    slack: SourceUserCount
    github: SourceUserCount
    confluence: SourceUserCount


class UserSyncMapping(BaseModel):
    name: str
    githubLogin: Optional[str] = None
    atlassianEmail: Optional[EmailStr] = None
    slackEmail: Optional[EmailStr] = None


class UserSyncStatusResponse(BaseModel):
    counts: SyncStatusCounts
    mappings: List[UserSyncMapping]
