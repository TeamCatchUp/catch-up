from __future__ import annotations

from collections.abc import Callable
from collections.abc import Mapping
from collections.abc import Sequence
from typing import TypeVar

import structlog

from catchup.sync.common.exceptions import SyncRequestException
from catchup.sync.common.schemas import FullSyncRequestedTarget
from catchup.sync.common.schemas import FullSyncResolvedTargets
from catchup.sync.common.schemas import FullSyncTarget
from catchup.sync.common.schemas import SyncTargetType

T = TypeVar("T")
logger = structlog.get_logger(__name__)


def _normalize_text(value: str | None) -> str:
    return (value or "").strip()


def _target_metadata(target: FullSyncRequestedTarget) -> dict[str, str]:
    return {
        "target_type": target.target_type.value,
        "target_id": target.target_id,
    }


def normalize_requested_targets(
    targets: Sequence[FullSyncRequestedTarget] | None,
) -> list[FullSyncRequestedTarget]:
    # API 요청과 내부 직접 호출 모두 여기서 같은 typed target 목록으로 정규화한다.
    # target_ids 호환 경로는 없으므로 None/empty는 명시적인 요청 오류다.
    if targets is None:
        raise SyncRequestException("targets is required")

    normalized: list[FullSyncRequestedTarget] = []
    seen: set[tuple[SyncTargetType, str]] = set()
    for item in targets:
        # 테스트나 scheduler가 dict 형태로 넘겨도 공통 dataclass 규칙을 통과시킨다.
        target = (
            item
            if isinstance(item, FullSyncRequestedTarget)
            else FullSyncRequestedTarget(
                target_type=item["target_type"],
                target_id=item["target_id"],
            )
        )
        key = (target.target_type, target.target_id)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(target)

    if not normalized:
        raise SyncRequestException(
            "targets is empty after normalization",
            metadata={"requested_targets": []},
        )

    return normalized


def require_requested_target_type(
    targets: Sequence[FullSyncRequestedTarget],
    *,
    target_type: SyncTargetType | str,
    error_metadata: Mapping[str, object],
) -> list[str]:
    # Slack/GitHub/Jira/Confluence처럼 target type이 하나인 connector는
    # ID 매칭 전에 type mismatch를 먼저 실패시킨다.
    normalized_type = SyncTargetType(target_type)
    invalid_targets = [
        _target_metadata(target)
        for target in targets
        if target.target_type != normalized_type
    ]
    if invalid_targets:
        raise SyncRequestException(
            "requested targets contain invalid target_type",
            metadata={
                **error_metadata,
                "expected_target_type": normalized_type.value,
                "invalid_targets": invalid_targets,
            },
        )
    return [target.target_id for target in targets]


def index_targets(
    rows: Sequence[T],
    *,
    key_getter: Callable[[T], str | None],
    log_context: Mapping[str, object] | None = None,
) -> dict[str, T]:
    # connector별 DB/API row를 target_id lookup table로 만든다.
    # blank/duplicate key는 요청자가 고른 target을 안전하게 해석할 수 없으므로 실패한다.
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
    target_type: SyncTargetType,
    target_index: Mapping[str, T],
    error_message: str,
    error_metadata: Mapping[str, object],
) -> list[T]:
    # 정규화된 요청 ID가 listing/snapshot row에 실제로 존재하는지 확인한다.
    # 에러 metadata는 프론트 계약과 같은 typed targets 형태로 남긴다.
    unknown_ids = [
        target_id
        for target_id in requested_ids
        if target_id not in target_index
    ]
    if unknown_ids:
        raise SyncRequestException(
            error_message,
            metadata={
                **error_metadata,
                "requested_targets": [
                    {
                        "target_type": target_type.value,
                        "target_id": target_id,
                    }
                    for target_id in requested_ids
                ],
                "invalid_targets": [
                    {
                        "target_type": target_type.value,
                        "target_id": target_id,
                    }
                    for target_id in unknown_ids
                ],
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
    # resolver가 확인한 row를 worker event seed로 변환 가능한 FullSyncTarget으로 만든다.
    # 여기서의 target_type/target_id가 이후 SyncEventSeed에 그대로 들어간다.
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
    request_targets: Sequence[FullSyncRequestedTarget] | None,
    rows: Sequence[T],
    target_type: SyncTargetType | str,
    key_getter: Callable[[T], str | None],
    name_getter: Callable[[T], str | None],
    error_message: str,
    error_metadata: Mapping[str, object],
    metadata_getter: Callable[[T], Mapping[str, object] | None] | None = None,
    log_context: Mapping[str, object] | None = None,
) -> tuple[list[str], FullSyncResolvedTargets]:
    # 단일 target type connector의 공통 resolver 흐름:
    # 요청 정규화 -> target_type 검증 -> row index 생성 -> ID 매칭 -> FullSyncTarget 생성.
    requested_targets = normalize_requested_targets(request_targets)
    normalized_type = SyncTargetType(target_type)
    requested_ids = require_requested_target_type(
        requested_targets,
        target_type=normalized_type,
        error_metadata=error_metadata,
    )
    target_index = index_targets(
        rows,
        key_getter=key_getter,
        log_context=log_context,
    )
    resolved_rows = resolve_requested_targets(
        requested_ids,
        target_type=normalized_type,
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
    return requested_ids, FullSyncResolvedTargets(targets=targets)
