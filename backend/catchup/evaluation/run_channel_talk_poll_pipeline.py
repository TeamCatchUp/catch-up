"""실제 ChannelTalk user chat을 폴링해 T1까지 확정한다.

`run_ingestion_pipeline.py`와 목적은 같고 입력이 다르다. 저쪽은 합성 payload
파일을 읽지만, 이 스크립트는 ChannelTalk Open API를 직접 찔러 바뀐 대화를
가져온다. 나중에 Dreaming Poller가 할 일을 손으로 돌려 보는 것이다.

증분 커서는 DB에서 도출한다. 이미 저장한 원문 중 가장 최신
`source_updated_at`에서 겹침 폭만큼 뒤로 물러난 시각이 이번 폴링의 시작점이다.
겹침을 두는 이유는 목록 API의 시각이 완전히 정렬되어 있다고 믿지 않기
때문이다. 저장한 원문이 아예 없으면 `--backfill-days` 전부터 훑는다.
`--since`를 주면 DB 도출을 건너뛰고 그 시각을 그대로 쓴다.

커서가 DB에서 도출되므로 부분 수집이 곧 영구 누락이 된다. 폴러가 못 집은
대화보다 최신인 대화를 저장하면 커서가 그 위로 올라가 다음 회차에도 빠진
대화를 찾지 못한다. 그래서 두 가드를 둔다. 변경 목록 자체가 잘렸으면 아무것도
넣지 않고 실패로 끝내고, 개별 대화가 빠졌으면 그 대화보다 오래된 것만 넣고
나머지는 다음 회차로 미룬다.

같은 대화를 다시 넣어도 idempotency key로 재사용되므로 여러 번 돌려도 안전하다.

개발과 평가 전용이다.

실행:
    uv run python -m catchup.evaluation.run_channel_talk_poll_pipeline \\
        --workspace-id 1
"""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Callable
from collections.abc import Sequence
from datetime import datetime
from datetime import timedelta
from datetime import timezone

from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker

from catchup.configs.config import settings
from catchup.connectors.channel_talk.core.client import ChannelTalkCoreApiClient
from catchup.connectors.channel_talk.credential_loader import (
    load_channel_talk_connection,
)
from catchup.knowledge_maintenance.adapters.connectors.channel_talk.observation_normalizer import (  # noqa: E501
    ChannelTalkUserChatNormalizer,
)
from catchup.knowledge_maintenance.adapters.connectors.channel_talk.user_chat_poller import (  # noqa: E501
    DEFAULT_STATES,
)
from catchup.knowledge_maintenance.adapters.connectors.channel_talk.user_chat_poller import (  # noqa: E501
    ChannelTalkUserChatPoller,
)
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)
from catchup.knowledge_maintenance.contracts.source_change import SourceChangeEnvelope
from catchup.knowledge_maintenance.ports.source_poller import SkippedItem
from catchup.knowledge_maintenance.services.ingest_and_normalize import (
    ingest_and_normalize,
)


def _parse_since(value: str) -> datetime:
    """`--since` 값을 ISO8601로 읽어 시간대를 붙인다.

    시간대가 없는 값은 UTC로 본다. 아래 커서 계산과 폴러가 모두 시간대를
    가진 시각끼리 비교하므로, 여기서 못 붙이면 뒤에서 비교가 터진다.
    """
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            f"ISO8601 시각이 아니다: {value!r} ({error})"
        ) from error
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _derive_lookback_start(
    session_factory: Callable[[], Session],
    *,
    workspace_id: int,
    args: argparse.Namespace,
) -> datetime:
    """이번 폴링이 어디서부터 훑을지 정한다.

    `--since`를 주면 DB를 보지 않고 그대로 쓴다. 수동 지정이 도출을 완전히
    덮어야 재수집 범위를 손으로 넓힐 수 있다.
    """
    if args.since is not None:
        return args.since
    with session_factory() as session:
        latest = session.execute(
            text(
                "SELECT max(source_updated_at) FROM source_versions "
                "WHERE workspace_id = :ws AND source_type = 'channel_talk'"
            ),
            {"ws": workspace_id},
        ).scalar()
    overlap = timedelta(minutes=max(0, args.lookback_overlap_minutes))
    if latest is not None:
        if latest.tzinfo is None:
            latest = latest.replace(tzinfo=timezone.utc)
        return latest.astimezone(timezone.utc) - overlap
    return datetime.now(timezone.utc) - timedelta(days=max(1, args.backfill_days))


def _split_by_barrier(
    envelopes: Sequence[SourceChangeEnvelope],
    skipped: Sequence[SkippedItem],
) -> tuple[list[SourceChangeEnvelope], list[SourceChangeEnvelope]]:
    """빠진 대화보다 최신인 envelope를 이번 회차에서 뺀다.

    커서는 저장된 원문의 최신 `source_updated_at`에서 도출된다. 그래서
    빠진 대화보다 최신인 대화를 먼저 저장하면 커서가 빠진 대화를 지나쳐
    다음 회차에도 집히지 않는다. 가장 오래된 빠진 대화의 기준 시각을
    장벽으로 두고, 그보다 오래된 것만 넣는다.

    기준 시각을 모르는 빠진 대화가 하나라도 있으면 장벽을 세울 수 없다.
    그 대화가 창의 어디에 있는지 모르므로 어떤 envelope도 안전하다고
    증명할 수 없어 전부 미룬다.
    """
    if not skipped:
        return list(envelopes), []

    markers = [item.ordering_marker for item in skipped]
    if any(marker is None for marker in markers):
        return [], list(envelopes)

    barrier = min(marker for marker in markers if marker is not None)
    ingest_now = [
        envelope
        for envelope in envelopes
        if envelope.source_updated_at < barrier
    ]
    held_back = [
        envelope
        for envelope in envelopes
        if envelope.source_updated_at >= barrier
    ]
    return ingest_now, held_back


def _parse_states(value: str) -> tuple[str, ...]:
    """쉼표로 이어 붙인 state 목록을 튜플로 쪼갠다."""
    states = tuple(item.strip() for item in value.split(",") if item.strip())
    if not states:
        raise argparse.ArgumentTypeError("state를 하나 이상 준다.")
    return states


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-id", type=int, required=True)
    parser.add_argument(
        "--since",
        type=_parse_since,
        default=None,
        help="ISO8601 시각. 주면 DB 커서 도출을 건너뛰고 이 시각부터 훑는다.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="한 번에 수집할 대화 수 상한이다.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=20,
        help="목록·메시지 조회의 페이지 수 상한이다.",
    )
    parser.add_argument(
        "--lookback-overlap-minutes",
        type=int,
        default=5,
        help="도출한 커서에서 뒤로 물러날 겹침 폭이다.",
    )
    parser.add_argument(
        "--backfill-days",
        type=int,
        default=30,
        help="저장한 원문이 없을 때 훑기 시작할 지점이다.",
    )
    parser.add_argument(
        "--states",
        type=_parse_states,
        default=DEFAULT_STATES,
        help="쉼표로 이어 붙인 user chat state 목록이다.",
    )
    return parser


async def main() -> None:
    args = _build_parser().parse_args()

    connection = load_channel_talk_connection()
    if connection is None:
        raise SystemExit(
            "ChannelTalk 연결이 없다 — channel_talk 자격증명을 먼저 등록한다."
        )
    if not connection.access_key or not connection.access_secret:
        raise SystemExit(
            f"ChannelTalk 자격증명이 비어 있다: channel {connection.channel_id} — "
            "access_key/access_secret을 다시 등록한다."
        )

    engine = create_engine(settings.sqlalchemy_database_url)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    lookback_start = _derive_lookback_start(
        session_factory,
        workspace_id=args.workspace_id,
        args=args,
    )
    print(
        f"channel {connection.channel_id} — "
        f"{lookback_start.isoformat()} 이후, state {','.join(args.states)}, "
        f"최대 {args.limit}건"
    )

    poller = ChannelTalkUserChatPoller(
        client=ChannelTalkCoreApiClient(),
        access_key=connection.access_key,
        access_secret=connection.access_secret,
        channel_id=connection.channel_id,
    )
    poll_result = await poller.poll(
        workspace_id=args.workspace_id,
        lookback_start=lookback_start,
        limit=args.limit,
        max_pages=args.max_pages,
        states=args.states,
    )

    if poll_result.list_truncated:
        # 목록이 잘렸으면 창 하단에 무엇이 남았는지조차 모른다. 이 상태로
        # 한 건이라도 넣으면 커서가 못 본 대화를 지나쳐 영구 누락이 된다.
        print(
            "  오류: 변경 목록이 페이지 상한에 잘렸다 — 창 하단이 잘렸다. "
            "아무것도 넣지 않는다. `--max-pages`를 늘리거나 `--since`로 "
            "범위를 좁혀 다시 돌린다."
        )
        engine.dispose()
        raise SystemExit(1)

    envelopes, held_back = _split_by_barrier(
        poll_result.envelopes,
        poll_result.skipped,
    )

    if len(poll_result.envelopes) >= args.limit:
        # limit에 걸리면 이번 회차가 창 전체를 다 보지 못했다는 뜻이다.
        # 커서는 이번에 넣은 대화의 최신 시각까지만 나아가므로, 남은
        # 대화는 러너를 다시 돌려야 집힌다.
        print(
            f"  주의: limit {args.limit}건에 걸렸다 — 이번 폴링은 잘렸을 수 "
            "있다. 남은 대화를 집으려면 러너를 다시 돌린다."
        )

    for item in poll_result.skipped:
        print(f"  {item.item_id}  건너뜀  {item.reason}")
    if held_back:
        print(
            f"  보류 {len(held_back)}건 — 실패 대화보다 최신이라 커서 안전을 "
            "위해 다음 회차로 미룬다."
        )
        if any(item.ordering_marker is None for item in poll_result.skipped):
            print(
                "    건너뛴 대화의 기준 시각을 몰라 창의 어디에 있는지 알 수 "
                "없다. 안전을 증명할 수 없어 전부 미룬다."
            )

    if not envelopes:
        print("이번 회차에 넣을 대화가 없다.")
        engine.dispose()
        return

    normalizer = ChannelTalkUserChatNormalizer()
    summary: dict[str, int] = {}
    failed = 0
    for envelope in envelopes:
        chat_id = envelope.source_identity.external_document_id
        # envelope마다 새 UoW를 쓴다. 대화 하나의 실패가 앞서 확정한
        # 대화까지 되돌리지 않게 하려면 트랜잭션이 서로 독립해야 한다.
        try:
            result = ingest_and_normalize(
                envelope,
                normalizer=normalizer,
                uow=KnowledgeMaintenanceUnitOfWork(session_factory),
            )
        except Exception as error:
            # 한 대화의 충돌이나 정규화 실패로 남은 대화를 버리지 않는다.
            # 실패한 대화는 이번 회차에서 빠지고, 커서가 그 시각을 이미
            # 지나갔으면 다음 회차에도 안 집힌다. 그래서 조용히 넘기지 않고
            # 대화 id까지 찍어 사람이 `--since`로 되돌릴 수 있게 한다.
            failed += 1
            print(f"  {chat_id}  실패  {type(error).__name__}: {error}")
            continue
        label = f"{result.ingestion.value}/{result.normalization.value}"
        summary[label] = summary.get(label, 0) + 1
        print(f"  {chat_id}  {label}  observation {str(result.observation_id)[:8]}")

    print("\n=== 수집 결과 ===")
    for label, count in sorted(summary.items()):
        print(f"  {label}: {count}")
    if failed:
        print(
            f"  실패 {failed}건 — 이번 회차에서 건너뛴 대화다. 커서가 이미 "
            "지나갔을 수 있으니 위에 찍힌 시각 이전으로 `--since`를 주어 "
            "다시 돌린다."
        )
    if poll_result.skipped:
        print(
            f"  건너뜀 {len(poll_result.skipped)}건 — 폴러가 수집하지 못한 대화다."
        )
    if held_back:
        print(
            f"  보류 {len(held_back)}건 — 커서가 이 대화들 아래에 머무르므로 "
            "다음 회차에 다시 집힌다."
        )
    print(
        f"  대화 {len(envelopes)}건, 끝난 시각 {datetime.now(timezone.utc).isoformat()}"
    )

    engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
