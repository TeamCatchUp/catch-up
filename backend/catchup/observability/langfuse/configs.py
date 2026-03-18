import structlog

from catchup.configs.config import settings

logger = structlog.get_logger()

_langfuse_client = None

if settings.ENABLE_LANGFUSE:
    try:
        from langfuse import get_client
        _langfuse_client = get_client()
        logger.info(
            "langfuse_client_init",
            status="success"
        )
        
    except Exception as e:
        logger.error(
            "langfuse_client_init",
            status="failed",
            error=str(e)
        )
        settings.ENABLE_LANGFUSE = False # 실패 시 플래그 강제 종료
        

if settings.ENABLE_LANGFUSE:
    from langfuse import observe as _observe
else:
    def _observe(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

observe = _observe


def get_langfuse_client():
    """
    시스템 전역 Langfuse Client를 반환한다.
    """
    if settings.ENABLE_LANGFUSE and _langfuse_client is not None:
        return _langfuse_client
    return None

