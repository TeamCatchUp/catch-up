import logging
from langchain_core.output_parsers import StrOutputParser
from catchup.components.llm.factory import LlmProvider, get_llm_service
from catchup.prompts.loader import prompt_loader

logger = logging.getLogger(__name__)

async def generate_chat_room_title(query: str) -> str:
    """채팅방 제목 생성"""
    llm = get_llm_service(LlmProvider.OPENAI).get_llm()
    prompt = prompt_loader.get_prompt(
        "chat/summarize_title.j2",
        query=query
    )
    
    chain = llm | StrOutputParser()
    
    try:
        generated_title = await chain.ainvoke(input=prompt)
        cleaned_title = generated_title.strip().replace('"', '').replace("'", "")
        return cleaned_title[:25]

    except Exception as e:
        logger.warning(f"Failed to generate chat room title from query: {e}")
        return query[:30] + "..." if len(query) > 30 else query
    
    
