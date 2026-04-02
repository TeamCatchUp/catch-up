from __future__ import annotations

from uuid import uuid4


def consumer_name() -> str:
    return f"sync-worker-{uuid4().hex[:8]}"