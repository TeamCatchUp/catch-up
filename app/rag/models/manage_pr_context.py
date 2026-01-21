from pydantic import BaseModel, Field

from app.rag.models.retrieve import PullRequestSearchResult

class PullRequestCandidate(BaseModel):
    id: int = Field(default="", description="pr_number")
    pr_number: int = Field(default=0)
    title: str = Field(default="")
    repo: str = Field(default="")
    summary: str = Field(default="")
    owner: str = Field(default="")
    created_at: int = Field(default=0)
    
    @classmethod
    def from_search_result_doc(
        cls,
        res: PullRequestSearchResult
    ) -> "PullRequestCandidate":
        return cls(
            id = res.id,
            pr_number = res.pr_number,
            title = res.title,
            repo = res.repo,
            summary = res.body[:100] if res.body else "",
            owner=res.owner,
            created_at=res.created_at
        )


class PullRequestUserSelected(BaseModel): 
    pr_number: int = Field(default=0)
    repo: str = Field(default="")
    owner: str = Field(default="")