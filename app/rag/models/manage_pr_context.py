from pydantic import BaseModel, Field

from app.rag.models.retrieve import PullRequestSearchResult

class PullRequestCandidate(BaseModel):
    id: str = Field(default="")
    pr_number: int = Field(default=0)
    title: str = Field(default="")
    repo_name: str = Field(default="")
    summary: str = Field(default="")
    
    @classmethod
    def from_search_result_doc(
        cls,
        res: PullRequestSearchResult
    ) -> "PullRequestCandidate":
        return cls(
            id = res.id,
            pr_number = res.pr_number,
            title = res.title,
            repo_name = res.repo_name,
            summary = res.body[:100] if res.body else ""
        )
    

class PullRequestSelected(BaseModel): 
    id: str 