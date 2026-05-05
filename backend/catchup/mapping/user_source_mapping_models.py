from enum import StrEnum

from pydantic import BaseModel


class UserSourceMappingStatus(StrEnum):
    ALL = "all"
    FULL = "full"
    PARTIAL = "partial"


class MappedSourceInfo(BaseModel):
    name: str | None = None
    identifier: str | None = None
    picture: str | None = None


class UserSourceMappingItem(BaseModel):
    user_id: int
    sub: str | None = None
    name: str
    email: str
    atlassian: MappedSourceInfo | None = None
    slack: MappedSourceInfo | None = None
    github: MappedSourceInfo | None = None
    confluence: MappedSourceInfo | None = None
    channel_talk: MappedSourceInfo | None = None


class UserSourceMappingResponse(BaseModel):
    total: int
    page: int
    size: int
    items: list[UserSourceMappingItem]


class MappingStatusCount(BaseModel):
    users: int
    mapped: int


class MappingStatusResponse(BaseModel):
    jira: MappingStatusCount
    slack: MappingStatusCount
    github: MappingStatusCount
    confluence: MappingStatusCount
    channel_talk: MappingStatusCount


class UserSourceMappingRefreshResponse(BaseModel):
    scanned_users: int
    inserted: dict[str, int]
    skipped_existing: dict[str, int]
    not_found: dict[str, int]
