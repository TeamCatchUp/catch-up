from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from catchup.worker.worker_event_processor import SyncWorker
    from catchup.worker.worker_event_processor import run_forever


def __getattr__(name: str):
    if name in __all__:
        from catchup.worker.worker_event_processor import SyncWorker
        from catchup.worker.worker_event_processor import run_forever

        return {
            "SyncWorker": SyncWorker,
            "run_forever": run_forever,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["SyncWorker", "run_forever"]
