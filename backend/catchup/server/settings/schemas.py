from pydantic import BaseModel

class PromptUpdate(BaseModel):
    custom_prompt: str | None