from typing import Generic, TypeVar
from pydantic import BaseModel, Field

# 제네릭 선언
T = TypeVar("T")

class BasePagination(BaseModel, Generic[T]):
    total: int = Field(..., description="전체 아이템 개수")
    page: int = Field(..., description="현재 페이지 번호")
    size: int = Field(..., description="페이지 당 아이템 개수")
    items: list[T] = Field(..., description="데이터 목록")