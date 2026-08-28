"""ChannelTalk 합성 payload를 수집해 Observation과 큐 지시를 남긴다.

`run_extraction_pipeline.py`의 앞 단계다. 저쪽이 큐에 쌓인 Observation을
추출한다면, 이 스크립트는 payload 파일을 `SourceChangeEnvelope`로 감싸
T1(원문 + Observation + 큐 지시)을 확정한다. 운영에서 Dreaming Poller가
할 일을 손으로 돌려 보는 것이다.

같은 payload를 다시 넣으면 idempotency key로 재사용되므로 여러 번 돌려도
안전하다. payload가 없으면 먼저 아래를 돌린다.

    uv run python -m catchup.evaluation.build_channel_talk_payloads

개발과 평가 전용이다.

실행:
    uv run python -m catchup.evaluation.run_ingestion_pipeline
"""

from __future__ import annotations

import argparse
from datetime import datetime
from datetime import timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from catchup.configs.config import settings
from catchup.knowledge_maintenance.adapters.connectors.channel_talk.observation_normalizer import (
    CHANNEL_TALK_USER_CHAT_MEDIA_TYPE,
)
from catchup.knowledge_maintenance.adapters.connectors.channel_talk.observation_normalizer import (
    ChannelTalkUserChatNormalizer,
)
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)
from catchup.knowledge_maintenance.contracts.source_change import SourceChangeEnvelope
from catchup.knowledge_maintenance.contracts.source_change import SourceIdentityPayload
from catchup.knowledge_maintenance.domain.source_version import ChangeKind
from catchup.knowledge_maintenance.services.ingest_and_normalize import (
    ingest_and_normalize,
)

DEFAULT_PAYLOAD_DIR = (
    Path(__file__).parent.parent / "experiments" / "channel_talk" / "payload"
)
SOURCE_TYPE = "channel_talk"


def _envelope(
    path: Path,
    *,
    workspace_id: int,
    observed_at: datetime,
) -> SourceChangeEnvelope:
    """payload 파일 하나를 poller가 만들었을 envelope로 감싼다."""
    key = path.stem
    return SourceChangeEnvelope(
        schema_version=1,
        event_id=f"{key}-created",
        workspace_id=workspace_id,
        source_type=SOURCE_TYPE,
        source_identity=SourceIdentityPayload(
            entity_type="user_chat",
            scope_id="ch-catchup-eval",
            target_id="ch-catchup-eval",
            external_document_id=key,
        ),
        change_kind=ChangeKind.CREATED,
        source_version_key="1",
        content=path.read_text(encoding="utf-8"),
        content_type=CHANNEL_TALK_USER_CHAT_MEDIA_TYPE,
        observed_at=observed_at,
        idempotency_key=f"{key}-1",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-id", type=int, default=1)
    parser.add_argument(
        "--payload-dir",
        type=Path,
        default=DEFAULT_PAYLOAD_DIR,
    )
    args = parser.parse_args()

    paths = sorted(args.payload_dir.glob("*.json"))
    if not paths:
        raise SystemExit(
            f"payload가 없다: {args.payload_dir} — "
            "build_channel_talk_payloads를 먼저 돌린다."
        )

    engine = create_engine(settings.sqlalchemy_database_url)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    normalizer = ChannelTalkUserChatNormalizer()
    observed_at = datetime.now(timezone.utc)

    summary: dict[str, int] = {}
    for path in paths:
        result = ingest_and_normalize(
            _envelope(path, workspace_id=args.workspace_id, observed_at=observed_at),
            normalizer=normalizer,
            uow=KnowledgeMaintenanceUnitOfWork(session_factory),
        )
        label = f"{result.ingestion.value}/{result.normalization.value}"
        summary[label] = summary.get(label, 0) + 1
        print(f"  {path.stem}  {label}  observation {str(result.observation_id)[:8]}")

    print("\n=== 수집 결과 ===")
    for label, count in sorted(summary.items()):
        print(f"  {label}: {count}")

    engine.dispose()


if __name__ == "__main__":
    main()
