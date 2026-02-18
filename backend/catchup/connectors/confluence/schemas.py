from pydantic import BaseModel, Field, model_validator


class ConfluenceSpaceDescription(BaseModel):
    plain: dict | None = None
    view: dict | None = None

    def get_plain_text(self) -> str:
        if self.plain and isinstance(self.plain.get("value"), str):
            return self.plain["value"]
        return ""

class ConfluenceSpaceResponse(BaseModel):
    id: str
    key: str
    name: str
    type: str
    status: str
    homepage_id: str | None = Field(default=None, alias="homepageId")
    description: ConfluenceSpaceDescription | None = None

    model_config = {"populate_by_name": True}


class ConfluenceUserResponse(BaseModel):
    id: str = Field(alias="accountId")
    account_type: str | None = Field(default=None, alias="accountType")
    display_name: str | None = Field(default=None, alias="displayName")
    public_name: str | None = Field(default=None, alias="publicName")
    email: str | None = Field(default=None, alias="email")
    time_zone: str | None = Field(default=None, alias="timeZone")
    locale: str | None = None
    profile_picture: dict | None = Field(default=None, alias="profilePicture")
    is_external_collaborator: bool | None = Field(default=None, alias="isExternalCollaborator")

    model_config = {"populate_by_name": True}

    def get_avatar_url(self) -> str | None:
        if self.profile_picture and isinstance(self.profile_picture.get("path"), str):
            return self.profile_picture["path"]
        return None


class ConfluenceRoleResponse(BaseModel):
    id: str
    key: str | None = None
    name: str | None = None


class ConfluenceRoleAssignmentResponse(BaseModel):
    id: str
    principal_id: str = Field(alias="principalId")
    principal_type: str = Field(alias="principalType")
    role: ConfluenceRoleResponse

    model_config = {"populate_by_name": True}

class ConfluenceVersion(BaseModel):
    """콘텐츠 버전 정보"""
    number: int
    created_at: str | None = Field(default=None, alias="createdAt")
    message: str | None = None
    minor_edit: bool = Field(default=False, alias="minorEdit")
    author_id: str | None = Field(default=None, alias="authorId")

    model_config = {"populate_by_name": True}

class ConfluenceBody(BaseModel):
    """콘텐츠 본문 (atlas_doc_format 또는 storage)"""
    representation: str | None = None
    value: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _extract_nested_body(cls, data):
        """
        Confluence v2 API는 body를 format 키로 감싸서 반환:
        {"storage": {"representation": "storage", "value": "..."}}
        → {"representation": "storage", "value": "..."} 로 평탄화
        """
        if isinstance(data, dict):
            for key in ("storage", "atlas_doc_format", "view", "export_view"):
                if key in data and isinstance(data[key], dict):
                    return data[key]
        return data


class ConfluencePageResponse(BaseModel):
    """Page 응답 스키마 (v2 API)"""
    id: str
    status: str
    title: str
    space_id: str | None = Field(default=None, alias="spaceId")
    parent_id: str | None = Field(default=None, alias="parentId")
    parent_type: str | None = Field(default=None, alias="parentType")
    position: int | None = None
    author_id: str | None = Field(default=None, alias="authorId")
    owner_id: str | None = Field(default=None, alias="ownerId")
    created_at: str | None = Field(default=None, alias="createdAt")
    version: ConfluenceVersion | None = None
    body: ConfluenceBody | None = None
    links: dict | None = Field(default=None, alias="_links")

    model_config = {"populate_by_name": True}

    def get_web_url(self) -> str | None:
        if self.links:
            return self.links.get("webui")
        return None


class ConfluenceBlogPostResponse(BaseModel):
    """BlogPost 응답 스키마 (v2 API)"""
    id: str
    status: str
    title: str
    space_id: str | None = Field(default=None, alias="spaceId")
    author_id: str | None = Field(default=None, alias="authorId")
    created_at: str | None = Field(default=None, alias="createdAt")
    version: ConfluenceVersion | None = None
    body: ConfluenceBody | None = None
    links: dict | None = Field(default=None, alias="_links")

    model_config = {"populate_by_name": True}

    def get_web_url(self) -> str | None:
        if self.links:
            return self.links.get("webui")
        return None


class ConfluenceCommentResponse(BaseModel):
    """Comment 응답 스키마 (footer / inline 공용, v2 API)"""
    id: str
    status: str
    title: str | None = None
    body: ConfluenceBody | None = None
    version: ConfluenceVersion | None = None
    created_at: str | None = Field(default=None, alias="createdAt")
    author_id: str | None = Field(default=None, alias="authorId")
    # inline comment 전용 필드
    resolution_status: str | None = Field(default=None, alias="resolutionStatus")
    parent_comment_id: str | None = Field(default=None, alias="parentCommentId")
    properties: dict | None = None
    links: dict | None = Field(default=None, alias="_links")

    model_config = {"populate_by_name": True}


class ConfluenceAttachmentResponse(BaseModel):
    """Attachment 응답 스키마 (v2 API)"""
    id: str
    status: str
    title: str
    media_type: str | None = Field(default=None, alias="mediaType")
    file_size: int | None = Field(default=None, alias="fileSize")
    created_at: str | None = Field(default=None, alias="createdAt")
    version: ConfluenceVersion | None = None
    download_link: str | None = Field(default=None, alias="downloadLink")
    links: dict | None = Field(default=None, alias="_links")

    model_config = {"populate_by_name": True}

    def get_download_url(self) -> str | None:
        if self.download_link:
            return self.download_link
        if self.links:
            return self.links.get("download")
        return None


class ConfluenceLabelResponse(BaseModel):
    """Label 응답 스키마 (v2 API)"""
    id: str
    prefix: str | None = None
    name: str