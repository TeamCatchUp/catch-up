from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import TypeVar
import structlog

from catchup.sync.common.exceptions import SyncRequestException
from catchup.sync.common.schemas import (
    FullSyncResolvedTargets,
    FullSyncTarget,
    SyncTargetType,
)

T = TypeVar("T")
logger = structlog.get_logger(__name__)


def _normalize_text(value: str | None) -> str:
    return (value or "").strip()


def normalize_target_ids(target_ids: list[str] | None) -> list[str]:
    if target_ids is None:
        raise SyncRequestException("target_ids is required")

    normalized: list[str] = []
    seen: set[str] = set()
    for item in target_ids:
        candidate = _normalize_text(item)
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        normalized.append(candidate)

    if not normalized:
        raise SyncRequestException(
            "target_ids is empty after normalization",
            metadata={"requested_target_ids": target_ids},
        )

    return normalized


def index_targets(
    rows: Sequence[T],
    *,
    key_getter: Callable[[T], str | None],
    log_context: Mapping[str, object] | None = None,
) -> dict[str, T]:
    index: dict[str, T] = {}
    blank_key_count = 0
    duplicate_key_count = 0
    duplicate_key_samples: list[str] = []
    context = dict(log_context or {})

    for row in rows:
        key = _normalize_text(key_getter(row))
        if not key:
            blank_key_count += 1
            continue
        if key in index:
            duplicate_key_count += 1
            if len(duplicate_key_samples) < 5:
                duplicate_key_samples.append(key)
            continue
        index[key] = row

    if blank_key_count:
        logger.warning(
            "sync_target_key_blank",
            count=blank_key_count,
            **context,
        )
        raise SyncRequestException(
            "resolved target rows contain blank target_id",
            metadata={
                **context,
                "blank_target_key_count": blank_key_count,
            },
        )

    if duplicate_key_samples:
        logger.warning(
            "sync_target_key_duplicate",
            count=duplicate_key_count,
            sample_keys=duplicate_key_samples,
            **context,
        )
        raise SyncRequestException(
            "resolved target rows contain duplicate target_id",
            metadata={
                **context,
                "duplicate_target_key_count": duplicate_key_count,
                "duplicate_target_key_samples": duplicate_key_samples,
            },
        )

    return index


def resolve_requested_targets(
    requested_ids: Sequence[str],
    *,
    target_index: Mapping[str, T],
    error_message: str,
    error_metadata: Mapping[str, object],
) -> list[T]:
    unknown_target_ids = [
        target_id
        for target_id in requested_ids
        if target_id not in target_index
    ]
    if unknown_target_ids:
        raise SyncRequestException(
            error_message,
            metadata={
                **error_metadata,
                "requested_target_ids": list(requested_ids),
                "invalid_target_ids": unknown_target_ids,
            },
        )

    return [target_index[target_id] for target_id in requested_ids]


def build_full_sync_targets(
    rows: Sequence[T],
    *,
    target_type: SyncTargetType | str,
    id_getter: Callable[[T], str | None],
    name_getter: Callable[[T], str | None],
    metadata_getter: Callable[[T], Mapping[str, object] | None] | None = None,
) -> list[FullSyncTarget]:
    normalized_type = SyncTargetType(target_type)
    targets: list[FullSyncTarget] = []

    for row in rows:
        target_id = _normalize_text(id_getter(row))
        if not target_id:
            raise SyncRequestException("resolved target_id is empty")

        target_name = _normalize_text(name_getter(row)) or target_id
        metadata = dict(metadata_getter(row) or {}) if metadata_getter is not None else {}

        targets.append(
            FullSyncTarget(
                target_type=normalized_type,
                target_id=target_id,
                target_name=target_name,
                metadata=metadata,
            )
        )

    return targets


def resolve_full_sync_targets_from_rows(
    *,
    request_target_ids: list[str] | None,
    rows: Sequence[T],
    target_type: SyncTargetType | str,
    key_getter: Callable[[T], str | None],
    name_getter: Callable[[T], str | None],
    error_message: str,
    error_metadata: Mapping[str, object],
    metadata_getter: Callable[[T], Mapping[str, object] | None] | None = None,
    log_context: Mapping[str, object] | None = None,
) -> tuple[list[str], FullSyncResolvedTargets]:
    requested_target_ids = normalize_target_ids(request_target_ids)
    target_index = index_targets(
        rows,
        key_getter=key_getter,
        log_context=log_context,
    )
    resolved_rows = resolve_requested_targets(
        requested_target_ids,
        target_index=target_index,
        error_message=error_message,
        error_metadata=error_metadata,
    )
    targets = build_full_sync_targets(
        resolved_rows,
        target_type=target_type,
        id_getter=key_getter,
        name_getter=name_getter,
        metadata_getter=metadata_getter,
    )
    return requested_target_ids, FullSyncResolvedTargets(targets=targets)
