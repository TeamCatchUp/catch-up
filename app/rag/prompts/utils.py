from langchain_core.prompts import ChatPromptTemplate

from app.rag.prompts.grade import DOCUMENT_GRADE_PROMPT
from app.rag.prompts.rewrite import REWRITE_PROMPT
from app.rag.prompts.plan import PLANNER_PROMPT


def get_prompt_template(prompt_name: str) -> ChatPromptTemplate:
    prompts = {
        "plan": PLANNER_PROMPT,
        "rewrite": REWRITE_PROMPT,
        "grade": DOCUMENT_GRADE_PROMPT,
    }

    prompt_str = prompts.get(prompt_name, "")
    return ChatPromptTemplate.from_template(prompt_str)
