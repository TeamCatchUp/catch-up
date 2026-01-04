from pydantic import BaseModel, Field


# 검색 결과에 대한 평가 담당 LLM 응답 양식
class GradeDocuments(BaseModel):
    binary_score: str = Field(
        description="Relevance score: 'yes' if relevant, or 'no' if not relevant"
    )
