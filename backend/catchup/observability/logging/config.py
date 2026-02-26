from __future__ import annotations

import logging
from typing import Final

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

def _resolve_log_level() -> int:
    return LOG_LEVELS[settings.LOG_LEVEL.upper()]

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

    # 최종 출력 형식 JSON 포맷팅
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
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


