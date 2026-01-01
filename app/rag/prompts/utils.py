from langchain_core.prompts import ChatPromptTemplate

from app.rag.prompts.grade import DOCUMENT_GRADE_PROMPT
from app.rag.prompts.rewrite import REWRITE_PROMPT
from app.rag.prompts.system import SYSTEM_ASSISTANT_PROMPT, SYSTEM_QUERY_ROUTER_PROMPT


def get_prompt_template(prompt_name: str) -> ChatPromptTemplate:
    prompts = {
        "rewrite": REWRITE_PROMPT,
        "system": SYSTEM_ASSISTANT_PROMPT,
        "grade": DOCUMENT_GRADE_PROMPT,
    }

    prompt_str = prompts.get(prompt_name, "")
    return ChatPromptTemplate.from_template(prompt_str)
