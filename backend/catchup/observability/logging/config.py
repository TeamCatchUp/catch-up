from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Final
import structlog

from catchup.configs.config import settings
from catchup.observability.logging.constants import (
    CONSOLE_EXCLUDE_KEYS,
    LOG_LEVELS,
)
from catchup.observability.logging.processors import (
    ensure_required_fields_processor,
    sanitize_secrets_processor,
    truncate_large_fields_processor,
)


SHARED_PROCESSORS: Final[list[Any]] = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    sanitize_secrets_processor,
    truncate_large_fields_processor,
    ensure_required_fields_processor,
]


def _resolve_log_level() -> int:
    return LOG_LEVELS[settings.LOG_LEVEL.upper()]


def _reorder_console_logger(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    logger_name = event_dict.pop("logger", None)
    if logger_name:
        event = event_dict.get("event", "")
        event_dict["event"] = f"[{logger_name}] {event}"
    return event_dict


def _drop_console_noise_fields(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    for key in CONSOLE_EXCLUDE_KEYS:
        event_dict.pop(key, None)

    # actor가 없는 경우에는 콘솔에 출력하지 않음
    actor = event_dict.get("actor")
    if not actor or (isinstance(actor, dict)) and not any(actor.values()):
        event_dict.pop("actor", None)

    return event_dict


def _build_console_handler() -> logging.Handler:
    """
    콘솔 출력 Formatter
    """
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=SHARED_PROCESSORS,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
            _reorder_console_logger,
            _drop_console_noise_fields,
            structlog.processors.ExceptionPrettyPrinter(),
            structlog.dev.ConsoleRenderer(
                colors=True,
                sort_keys=False,
                pad_level=False,
            ),
        ],
    )
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    return handler


def _build_json_file_handler() -> logging.Handler:
    log_path = Path(settings.LOG_JSON_FILE_PATH)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=SHARED_PROCESSORS,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
    )

    handler = RotatingFileHandler(
        filename = log_path,
        maxBytes = settings.LOG_JSON_MAX_BYTES,
        backupCount = settings.LOG_JSON_BACKUP_COUNT,
        encoding = "utf-8",
    )
    handler.setFormatter(formatter)
    return handler


def configure_logging() -> None:
    log_level = _resolve_log_level()

    handlers: list[logging.Handler] = []
    warnings: list[str] = []

    if settings.LOG_CONSOLE_ENABLED:
        handlers.append(_build_console_handler())
    
    if settings.LOG_JSON_FILE_ENABLED:
        try:
            handlers.append(_build_json_file_handler())
        except Exception as exc:
            warnings.append(
                f"[LOGGING][FILE HANDLER] Failed to initialize JSON File Handler :{exc}"
            )
    
    if not handlers:
        handlers.append(_build_console_handler())
        warnings.append(
            "[LOGGING][HANDLER_FALLBACK] No logging handlers available. Falling back to console."
        )
    
    # 루트 로거 장악
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    for handler in handlers:
        root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # httpx, httpcore에 대해서만 WARNING 이상의 로그만 표시되도록 설정
    logging.getLogger("catchup").setLevel(log_level)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    
    for name in ["uvicorn", "uvicorn.error", "fastapi"]:
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True  # 루트 로거로 출력 전파
        
    access_logger = logging.getLogger("uvicorn.access")
    access_logger.handlers.clear()
    access_logger.propagate = False

    structlog.configure(
        processors = SHARED_PROCESSORS + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    for message in warnings:
        logging.getLogger("catchup.observability.logging").warning(message)
