# [Development Use Only]
# 프롬프트 형상관리 도구로서 Langfuse를 선택 -> (클라우드) -> (로컬) 동기화 스크립트

import logging
import os
from langfuse import Langfuse

from catchup.configs.config import settings

logger = logging.getLogger(__name__)

# { "Langfuse_Prompt_Name": "Local_File_Path" }
PROMPT_MAPPING = {
    "rag/chitchat": "catchup/rag/prompts/chitchat.j2",
    # "rag/route_query": "catchup/rag/prompts/route_query.j2"
}

def sync_prompts():
    langfuse = Langfuse(
        public_key=settings.LANGFUSE_PUBLIC_KEY,
        secret_key=settings.LANGFUSE_SECRET_KEY,
    )
    
    print(f"Syncing prompts from Langfuse({settings.LANGFUSE_BASE_URL})")
    
    for lf_name, local_path in PROMPT_MAPPING.items():
        try:
            prompt = langfuse.get_prompt(lf_name, label="development")
        
            raw_content = prompt.prompt
            
            abs_path = os.path.join(os.getcwd(), local_path)
            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(raw_content)
                
            print(f"Sync succeeded: {lf_name} -> {local_path}")
        
        except Exception as e:
            print(f"Sync failed: {lf_name}: {e}")        
        
sync_prompts()