from pydantic import BaseModel
from pydantic import Field


class GradeResult(BaseModel):
    reusable: bool
    reason: str


class GuideDraft(BaseModel):
    """generate_guide_node의 LLM structured output 스키마다."""

    draft: str
    explanation: str
    cited_indices: list[int] = Field(default_factory=list)