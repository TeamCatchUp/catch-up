from __future__ import annotations

from catchup.sync.stream_runtime.stream_constants import STREAM_CLAIM_START_ID
from catchup.sync.stream_runtime.stream_queue import AckDeleteResult
from catchup.sync.stream_runtime.stream_queue import ack_messages
from catchup.sync.stream_runtime.stream_queue import autoclaim_stale_messages
from catchup.sync.stream_runtime.stream_queue import ensure_consumer_group
from catchup.sync.stream_runtime.stream_queue import read_new_messages
from catchup.sync.stream_runtime.stream_schemas import SyncStreamMessage


async def initialize_stream_runtime() -> None:
    await ensure_consumer_group()


async def read_ready_messages(
    *,
    consumer_name: str,
    reclaim_min_idle_ms: int,
    reclaim_start_id: str = STREAM_CLAIM_START_ID,
    reclaim_count: int = 100,
    read_count: int = 50,
    block_ms: int | None = None,
) -> tuple[list[SyncStreamMessage], str]:
    claim_batch = await autoclaim_stale_messages(
        consumer_name=consumer_name,
        min_idle_ms=reclaim_min_idle_ms,
        start_id=reclaim_start_id,
        count=reclaim_count,
    )
    new_messages = await read_new_messages(
        consumer_name=consumer_name,
        count=read_count,
        block_ms=block_ms,
    )

    if not claim_batch.messages:
        return new_messages, claim_batch.next_start_id
    if not new_messages:
        return claim_batch.messages, claim_batch.next_start_id

    merged_by_message_id: dict[str, SyncStreamMessage] = {}
    for message in claim_batch.messages:
        merged_by_message_id[message.message_id] = message
    for message in new_messages:
        merged_by_message_id[message.message_id] = message

    merged_messages = list(merged_by_message_id.values())
    return merged_messages, claim_batch.next_start_id


async def ack_consumed_messages(messages: list[SyncStreamMessage]) -> AckDeleteResult:
    message_ids = [message.message_id for message in messages]
    return await ack_messages(message_ids)
