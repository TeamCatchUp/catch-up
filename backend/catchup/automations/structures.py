from pydantic import BaseModel


class GradeResult(BaseModel):
    reusable: bool
    reason: str