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
