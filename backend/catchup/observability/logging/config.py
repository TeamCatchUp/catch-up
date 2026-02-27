from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Final

import structlog

from catchup.configs.config import settings
from catchup.observability.logging.processors import(
    ensure_required_fields_processor,
    sanitize_secrets_processor,
    truncate_large_fields_processor,
)

LOG_LEVELS: Final[dict[str, int]] = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
    "NOTSET": logging.NOTSET,
}

CONSOLE_EXCLUDE_KEYS: Final[set[str]] = {
    "actor",
    "environment",
    "event_action",
    "event_type",
    "metadata",
    "service",
    "trace_id",
    "version",
}

def _resolve_log_level() -> int:
    return LOG_LEVELS[settings.LOG_LEVEL.upper()]

def _reorder_console_logger(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    logger_name = event_dict.pop("logger", None) or event_dict.pop("logger_name", None)
    if not logger_name:
        return event_dict

    timestamp = event_dict.get("timestamp")
    if isinstance(timestamp, str):
        event_dict["timestamp"] = f"{timestamp} [{logger_name}]"
    else:
        event_dict["logger"] = logger_name

    return event_dict

def _drop_console_noise_fields(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    for key in CONSOLE_EXCLUDE_KEYS:
        event_dict.pop(key, None)
    return event_dict

def _build_console_handler(shared_processors: list[Any]) -> logging.Handler:
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            _reorder_console_logger,
            _drop_console_noise_fields,
            structlog.dev.ConsoleRenderer(),
        ],
    )
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    return handler

def _build_json_file_handler(shared_processors: list[Any]) -> logging.Handler:
    log_path = Path(settings.LOG_JSON_FILE_PATH)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
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

    shared_processors = [
        # 요청 컨텍스트 병합
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        # 예외 정보 문자열화
        structlog.processors.format_exc_info,
        # 커스텀 정책 적용
        sanitize_secrets_processor,
        truncate_large_fields_processor,
        ensure_required_fields_processor,
    ]

    handlers: list[logging.Handler] = []
    warnings: list[str] = []

    if settings.LOG_CONSOLE_ENABLED:
        handlers.append(_build_console_handler(shared_processors))
    
    if settings.LOG_JSON_FILE_ENABLED:
        try:
            handlers.append(_build_json_file_handler(shared_processors))
        except Exception as exc:
            warnings.append(
                f"[LOGGING][FILE HANDLER] Failed to initialize JSON File Handler :{exc}"
            )
    
    if not handlers:
        handlers.append(_build_console_handler(shared_processors))
        warnings.append(
            "[LOGGING][HANDLER_FALLBACK] No logging handlers available. Falling back to console."
        )
    
    root_logger = logging.getLogger()
    root_logger.handlers = handlers
    root_logger.setLevel(log_level)

    # httpx, httpcore에 대해서만 WARNING 이상의 로그만 표시되도록 설정
    logging.getLogger("catchup").setLevel(log_level)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    structlog.configure(
        processors = shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    for message in warnings:
        logging.getLogger("catchup.observability.logging").warning(message)
