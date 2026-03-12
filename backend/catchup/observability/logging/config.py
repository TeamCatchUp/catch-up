from __future__ import annotations

import logging
import structlog

from catchup.configs.config import settings
from catchup.observability.logging.handlers import (
    build_console_handler,
    build_json_file_handler,
    build_audit_file_handler,
)
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
        except Exception:
            warnings.append("handler_initialization_failed")
    
    if not handlers:
        handlers.append(build_console_handler())
        warnings.append("handler_initialization_failed")
        
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
    
    if settings.LOG_AUDIT_FILE_ENABLED:
        try:
            audit_logger.addHandler(build_audit_file_handler())
        except Exception:
            warnings.append("handler_initialization_failed")
            
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


# def configure_logging() -> None:
#     log_level = resolve_log_level()

#     handlers: list[logging.Handler] = []
#     warnings: list[str] = []

#     if settings.LOG_CONSOLE_ENABLED:
#         handlers.append(build_console_handler())

#     if settings.LOG_JSON_FILE_ENABLED:
#         try:
#             handlers.append(build_json_file_handler())
#         except Exception as exc:
#             warnings.append(
#                 f"[LOGGING][FILE HANDLER] Failed to initialize JSON File Handler :{exc}"
#             )

#     if not handlers:
#         handlers.append(build_console_handler())
#         warnings.append(
#             "[LOGGING][HANDLER_FALLBACK] No logging handlers available. Falling back to console."
#         )

#     # 루트 로거 장악
#     root_logger = logging.getLogger()
#     root_logger.handlers.clear()
#     for handler in handlers:
#         root_logger.addHandler(handler)
#     root_logger.setLevel(log_level)

#     # httpx, httpcore에 대해서만 WARNING 이상의 로그만 표시되도록 설정
#     logging.getLogger("catchup").setLevel(log_level)
#     logging.getLogger("httpx").setLevel(logging.WARNING)
#     logging.getLogger("httpcore").setLevel(logging.WARNING)

#     for name in ["uvicorn", "uvicorn.error", "fastapi"]:
#         logger = logging.getLogger(name)
#         logger.handlers.clear()
#         logger.propagate = True  # 루트 로거로 출력 전파

#     access_logger = logging.getLogger("uvicorn.access")
#     access_logger.handlers.clear()
#     access_logger.propagate = False

#     # catchup.audit 전용 로거 격리
#     audit_logger = logging.getLogger("catchup.audit")
#     audit_logger.handlers.clear()
#     audit_logger.setLevel(logging.INFO)  # 감사로그 유실 방지
#     audit_logger.propagate = False

#     # S3용 핸들러 적용
#     if settings.LOG_CONSOLE_ENABLED:
#         audit_logger.addHandler(build_console_handler())

#     if settings.LOG_AUDIT_FILE_ENABLED:
#         try:
#             audit_logger.addHandler(build_audit_file_handler())
#         except Exception as exc:
#             warnings.append(
#                 f"[LOGGING][AUDIT HANDLER] Failed to initialize Audit File Handler :{exc}"
#             )

#     structlog.configure(
#         processors=SHARED_PROCESSORS
#         + [
#             structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
#         ],
#         context_class=dict,
#         logger_factory=structlog.stdlib.LoggerFactory(),
#         wrapper_class=structlog.stdlib.BoundLogger,
#         cache_logger_on_first_use=True,
#     )

#     for message in warnings:
#         logging.getLogger("catchup.observability.logging").warning(message)
