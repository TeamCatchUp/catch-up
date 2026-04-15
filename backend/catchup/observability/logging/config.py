from __future__ import annotations

import logging

import structlog

from catchup.configs.config import settings
from catchup.observability.logging.handlers import build_audit_file_handler
from catchup.observability.logging.handlers import build_console_handler
from catchup.observability.logging.handlers import build_json_file_handler
from catchup.observability.logging.processors import SHARED_PROCESSORS
from catchup.observability.logging.utils import resolve_log_level


def _setup_root_logger(log_level: int) -> list[str]:
    warnings: list[str] = []
    handlers: list[logging.Handler] = []
    
    if settings.LOG_CONSOLE_ENABLED:
        handlers.append(build_console_handler())
    
    if settings.LOG_JSON_FILE_ENABLED:
        try:
            handlers.append(build_json_file_handler())
        except Exception as e:
            warnings.append(f"handler_initialization_failed: {str(e)}")
    
    if not handlers:
        handlers.append(build_console_handler())
        warnings.append("fallback_to_console_handler: no handlers configured")

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    for handler in handlers:
        root_logger.addHandler(handler)
    root_logger.setLevel(log_level)
    
    return warnings


def _setup_third_party_loggers(log_level: int) -> None:
    logging.getLogger("catchup").setLevel(log_level)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("botocore.parsers").setLevel(logging.WARNING)
    logging.getLogger("langchain_aws").setLevel(logging.INFO)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    for name in ["uvicorn", "uvicorn.error", "fastapi"]:
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True
        
    access_logger = logging.getLogger("uvicorn.access")
    access_logger.handlers.clear()
    access_logger.propagate = False
    

def _setup_audit_logger() -> list[str]:
    warnings: list[str] = []
    
    audit_logger = logging.getLogger("catchup.audit")
    audit_logger.handlers.clear()
    audit_logger.setLevel(logging.INFO)  # 감사 로그 유실 방지
    audit_logger.propagate = False
    
    if settings.LOG_CONSOLE_ENABLED:
        audit_logger.addHandler(build_console_handler())
        # TODO: 협의 후 활성화 또는 삭제
        # msg = resolve_console_exclude_keys(log_level)
        # if msg:
        #     warnings.append(msg)
    
    if settings.LOG_AUDIT_FILE_ENABLED:
        try:
            audit_logger.addHandler(build_audit_file_handler())
        except Exception as e:
            warnings.append(f"handler_initialization_failed: {str(e)}")
            
    return warnings


def _configure_structlog() -> None:
    structlog.configure(
        processors=SHARED_PROCESSORS + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
def configure_logging() -> None:
    log_level = resolve_log_level()
    warnings: list[str] = []
    
    warnings.extend(_setup_root_logger(log_level))
    _setup_third_party_loggers(log_level)
    warnings.extend(_setup_audit_logger())
    _configure_structlog()
    
    internal_logger = logging.getLogger("catchup.observability.logging")
    for message in warnings:
        internal_logger.warning(message)
