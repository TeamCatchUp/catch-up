from __future__ import annotations

import structlog

from catchup.db.models import SyncConnector
from catchup.sync.query.types import SyncTargetResult
from catchup.sync.query.types import SyncTargetsResult

logger = structlog.get_logger()


def build_targets_result(
    *,
    connector: SyncConnector,
    scope_id: str,
    targets: list[SyncTargetResult],
) -> SyncTargetsResult:
    logger.info(
        "sync_targets_loaded",
        connector=connector.value,
        scope_id=scope_id,
        total_targets=len(targets),
    )
    return SyncTargetsResult(
        connector=connector,
        scope_id=scope_id,
        total_targets=len(targets),
        targets=targets,
    )
