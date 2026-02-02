from pydantic import BaseModel, Field

from catchup.rag.schemas import PullRequestUserSelected


class ChatStreamingResumeRequest(BaseModel):
    session_id: str = Field(..., description="PR 수동 선택 후 재개할 세션 ID")
    user_selected_pull_requests: list[PullRequestUserSelected] = Field(
        ..., description="사용자가 선택한 PR 번호 리스트"
    )
