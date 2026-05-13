from __future__ import annotations

import argparse
import asyncio
import json

from catchup.sync.stream_runtime.startup_cleanup import SyncStreamStartupCleanupConfig
from catchup.sync.stream_runtime.startup_cleanup import run_startup_sync_stream_cleanup


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the guarded one-shot Redis sync stream cleanup.",
    )
    parser.add_argument("--version", default="manual_sync_stream_cleanup")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--retention-days", type=int, default=7)
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--max-batches", type=int, default=0)
    parser.add_argument("--lock-ttl-seconds", type=int, default=3600)
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    parser.add_argument("--dlq-maxlen", type=int, default=100000)
    parser.add_argument("--delete-orphaned-entries", action="store_true")
    return parser.parse_args()


async def _main() -> None:
    args = _parse_args()
    config = SyncStreamStartupCleanupConfig(
        version=args.version,
        dry_run=args.dry_run,
        retention_days=args.retention_days,
        batch_size=args.batch_size,
        max_batches=args.max_batches,
        lock_ttl_seconds=args.lock_ttl_seconds,
        sleep_seconds=args.sleep_seconds,
        dlq_maxlen=args.dlq_maxlen,
        delete_orphaned_entries=args.delete_orphaned_entries,
    )
    result = await run_startup_sync_stream_cleanup(config=config, trigger_path=None)
    print(json.dumps(result.to_log_fields(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(_main())
