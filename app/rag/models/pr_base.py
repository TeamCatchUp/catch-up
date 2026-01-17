from typing import Optional

from pydantic import BaseModel, Field


class PRComment(BaseModel):
    """PR 파일에 달린 개별 리뷰 코멘트 (최적화 버전)"""
    id: int
    author: str
    body: str
    created_at: str
    line: Optional[int] = Field(default=None, description="코멘트가 달린 라인 번호")
    original_line: Optional[int] = Field(default=None, description="코멘트 작성 시점의 라인 번호")


class PRFileContext(BaseModel):
    """PR에 포함된 파일의 변경 내역 및 코멘트 정보"""
    path: str = Field(description="파일 경로")
    status: str = Field(description="변경 상태 (modified, added, deleted, etc)")
    additions: int
    deletions: int
    previous_filename: Optional[str] = Field(default=None, description="Renaming의 경우 이전 파일 이름 포함")
    patch: str = Field(default="", description="변경된 코드 내용 (Diff)")
    comments: list[PRComment] = Field(default_factory=list, description="해당 파일에 달린 리뷰 코멘트 목록")