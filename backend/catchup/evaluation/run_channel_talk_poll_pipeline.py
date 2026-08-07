"""실제 ChannelTalk user chat을 폴링해 T1까지 확정한다.

`run_ingestion_pipeline.py`와 목적은 같고 입력이 다르다. 저쪽은 합성 payload
파일을 읽지만, 이 스크립트는 ChannelTalk Open API를 직접 찔러 바뀐 대화를
가져온다. 나중에 Dreaming Poller가 할 일을 손으로 돌려 보는 것이다.

증분 커서는 DB에서 도출한다. 이미 저장한 원문 중 가장 최신
`source_updated_at`에서 겹침 폭만큼 뒤로 물러난 시각이 이번 폴링의 시작점이다.
겹침을 두는 이유는 목록 API의 시각이 완전히 정렬되어 있다고 믿지 않기
때문이다. 저장한 원문이 아예 없으면 `--backfill-days` 전부터 훑는다.
`--since`를 주면 DB 도출을 건너뛰고 그 시각을 그대로 쓴다.

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
    envelopes = await poller.poll(
        workspace_id=args.workspace_id,
        lookback_start=lookback_start,
        limit=args.limit,
        max_pages=args.max_pages,
        states=args.states,
    )

    if not envelopes:
        print("바뀐 대화가 없다.")
        engine.dispose()
        return

    normalizer = ChannelTalkUserChatNormalizer()
    summary: dict[str, int] = {}
    for envelope in envelopes:
        # envelope마다 새 UoW를 쓴다. 대화 하나의 실패가 앞서 확정한
        # 대화까지 되돌리지 않게 하려면 트랜잭션이 서로 독립해야 한다.
        result = ingest_and_normalize(
            envelope,
            normalizer=normalizer,
            uow=KnowledgeMaintenanceUnitOfWork(session_factory),
        )
        label = f"{result.ingestion.value}/{result.normalization.value}"
        summary[label] = summary.get(label, 0) + 1
        chat_id = envelope.source_identity.external_document_id
        print(f"  {chat_id}  {label}  observation {str(result.observation_id)[:8]}")

    print("\n=== 수집 결과 ===")
    for label, count in sorted(summary.items()):
        print(f"  {label}: {count}")
    print(
        f"  대화 {len(envelopes)}건, 끝난 시각 {datetime.now(timezone.utc).isoformat()}"
    )

    engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
