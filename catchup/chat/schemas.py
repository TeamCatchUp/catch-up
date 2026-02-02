from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field

from catchup.rag.schemas import JiraSource, SourceResponse


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceResponse] = []
    process_time: float


class ChatStreamingResponse(BaseModel):
    type: Literal["status"] = "status"
    session_id: str
    node: str
    message: str


class ChatStreamingFinalResponse(BaseModel):
    type: Literal["result"] = "result"
    session_id: str
    node: str
    answer: str
    sources: list[SourceResponse] = []
    related_jira_issues: list[JiraSource] = []
    process_time: float


class ChatStreamingInterruptResponse(BaseModel):
    type: Literal["interrupt"] = "interrupt"
    session_id: str
    node: str
    payload: Any


class ChatStreamingKeepAliveResponse(BaseModel):
    type: Literal["ping"] = "ping"
    session_id: str


StreamEvent = Annotated[
    Union[
        ChatStreamingResponse,
        ChatStreamingFinalResponse,
        ChatStreamingInterruptResponse,
        ChatStreamingKeepAliveResponse,
    ],
    Field(discriminator="type"),
]
