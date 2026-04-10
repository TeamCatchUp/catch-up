from typing import Self

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import model_validator

from catchup.db.models import JobRole
from catchup.db.models import SelectedOption


class PromptSettingsRequest(BaseModel):
    job_role: JobRole | None = None
    custom_job_text: str | None = Field(default=None, max_length=50)
    job_description: str | None = Field(default=None, max_length=200)
    selected_options: list[SelectedOption] = Field(default_factory=list)
    custom_prompt: str | None = Field(default=None, max_length=500)
    
    @model_validator(mode="after")
    def validate_custom_fields(self) -> Self:
        if self.job_role == JobRole.CUSTOM and not self.custom_job_text:
            raise ValueError("job_role이 CUSTOM이면 custom_job_text가 필요합니다.")
        return self


class PromptSettingsResponse(BaseModel):
    job_role: JobRole | None = None
    custom_job_text: str | None = None
    job_description: str | None = None
    selected_options: list[SelectedOption] = []
    custom_prompt: str | None = None

    model_config = ConfigDict(from_attributes=True)
    
