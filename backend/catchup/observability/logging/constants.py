import logging
from typing import Final


SENSITIVE_KEYS = {
    "password",
    "passphrase",
    "authorization",
    "cookie",
    "set-cookie",
    "access_token",
    "refresh_token",
    "id_token",
    "token",
    "client_secret",
    "api_key",
    "secret",
    "private_key",
}

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
    "remote_addr",
}
