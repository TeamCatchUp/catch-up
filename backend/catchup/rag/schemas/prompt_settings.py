from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class PromptSettings(BaseModel):
    job_role: str | None = None
    custom_job_text: str | None = None
    job_description: str | None = None
    selected_options: list[str] = Field(default_factory=list)
    custom_prompt: str | None = None

    model_config = ConfigDict(from_attributes=True)