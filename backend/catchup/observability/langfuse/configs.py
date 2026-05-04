import structlog

from catchup.configs.config import settings

logger = structlog.get_logger()

_langfuse_client = None


def init_langfuse() -> None:
    global _langfuse_client
    
    if not settings.ENABLE_LANGFUSE:
        return

    try:
        from langfuse import Langfuse
        _langfuse_client = Langfuse(
            public_key=settings.LANGFUSE_PUBLIC_KEY,
            secret_key=settings.LANGFUSE_SECRET_KEY,
            base_url=settings.LANGFUSE_BASE_URL,
            timeout=settings.LANGFUSE_TIMEOUT,
        )
        logger.info(
            "langfuse_client_init",
            status="success",
            timeout=settings.LANGFUSE_TIMEOUT
        )
        
    except Exception as e:
        logger.error(
            "langfuse_client_init",
            status="failed",
            error=str(e)
        )
        settings.ENABLE_LANGFUSE = False
        

def _noop_observe(*args, **kwargs):
    def decorator(func):
        return func
    return decorator


def get_observe():
    if settings.ENABLE_LANGFUSE:
        from langfuse import observe
        return observe
    return _noop_observe


def get_langfuse_client():
    """
    시스템 전역 Langfuse Client를 반환한다.
    """
    if settings.ENABLE_LANGFUSE and _langfuse_client is not None:
        return _langfuse_client
    return None

