from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from catchup.db.models import JobRole
from catchup.db.models import ResponseStyleOption


class PromptUpdateRequest(BaseModel):
    job_role: JobRole | None = None
    custom_job_text: str | None = Field(default=None, max_length=50)
    job_description: str | None = Field(default=None, max_length=200)
    selected_options: list[ResponseStyleOption] = Field(default_factory=list)
    custom_prompt: str | None = Field(default=None, max_length=500)


class PromptSettingResponse(BaseModel):
    job_role: JobRole | None = None
    custom_job_text: str | None = None
    job_description: str | None = None
    selected_options: list[ResponseStyleOption] = []
    custom_prompt: str | None = None

    model_config = ConfigDict(from_attributes=True)
