import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path

import structlog

from catchup.configs.config import settings
from catchup.observability.logging.processors import SHARED_PROCESSORS
from catchup.observability.logging.utils import (
    drop_console_noise_fields,
    reorder_audit_keys,
    reorder_console_logger,
    unix_timestamp_namer,
)


def build_console_handler() -> logging.Handler:
    """
    콘솔 출력 핸들러
    """
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=SHARED_PROCESSORS,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
            reorder_console_logger,
            drop_console_noise_fields,
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


def build_json_file_handler() -> logging.Handler:
    """
    운영용 json 파일 출력 핸들러
    """

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
        filename=log_path,
        maxBytes=settings.LOG_JSON_MAX_BYTES,
        backupCount=settings.LOG_JSON_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(formatter)
    return handler


def build_audit_file_handler() -> logging.Handler:
    """
    감사 로그 전용 파일 핸들러 (S3 업로드용 롤링)
    """

    log_path = Path(settings.LOG_AUDIT_FILE_PATH)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=SHARED_PROCESSORS,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            reorder_audit_keys,
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
    )

    handler = TimedRotatingFileHandler(
        filename=log_path,
        when=settings.LOG_AUDIT_ROTATION_WHEN,
        interval=settings.LOG_AUDIT_ROTATION_INTERVAL,
        backupCount=settings.LOG_AUDIT_BACKUP_COUNT,
        encoding="utf-8",
    )
    
    handler.namer = unix_timestamp_namer
    handler.setFormatter(formatter)
    return handler
