from pydantic import BaseModel, Field


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
    type: str = "global"
    status: str = "current"
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
