from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from catchup.audit import sync as audit_sync
from catchup.db.models import SyncConnector, SyncType


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def emit_sync_dispatch_accepted(
    *,
    connector: SyncConnector,
    sync_type: SyncType,
    trigger: str,
    run_id: str,
    scope_id: str,
    counts: dict[str, int],
    scope_metadata: dict[str, Any] | None = None,
    actor: dict[str, Any] | None = None,
) -> None:
    connector_key = connector.value
    sync_type_value = sync_type.value
    connector_details = {"scope_id": scope_id, **dict(scope_metadata or {})}
    sync_details = {
        "phase": "api_accepted",
        "sync_type": sync_type_value,
        "event_at_utc": _utc_now_iso(),
    }

    if sync_type == SyncType.INCREMENTAL:
        audit_sync.incremental_sync(
            connector=connector_key,
            result="accepted",
            trigger=trigger,
            resource_type="resource",
            counts=counts,
            run_id=run_id,
            connector_details=connector_details,
            sync_details=sync_details,
            actor=actor,
        )
        return

    audit_sync.full_sync(
        connector=connector_key,
        result="accepted",
        sync_type=sync_type_value,
        trigger=trigger,
        resource_type="resource",
        counts=counts,
        run_id=run_id,
        connector_details=connector_details,
        sync_details=sync_details,
        actor=actor,
    )
