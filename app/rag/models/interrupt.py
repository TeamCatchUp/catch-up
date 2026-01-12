from pydantic import BaseModel

class PullRequestSource(BaseModel):
    prs: list[str]  # ex. #31