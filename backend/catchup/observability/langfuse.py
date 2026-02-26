import logging

from openai import max_retries, timeout

from catchup.configs.config import settings

logger = logging.getLogger(__name__)

langfuse_handler = None

if settings.ENABLE_LANGFUSE:
    try:
        from langfuse import get_client
        from langfuse.langchain import CallbackHandler

        langfuse = get_client()
        langfuse_handler = CallbackHandler()
        logger.info("Langfuse logging is enabled.")
        
    except Exception as e:
        logger.error(f"Failed to initialize Langfuse: {e}")
        settings.ENABLE_LANGFUSE = False # 실패 시 플래그 강제 종료
        

if settings.ENABLE_LANGFUSE:
    from langfuse import observe as _observe
else:
    def _observe(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

observe = _observe
