"""확정된 entity 병합 한 건을 손으로 되돌린다.

`run_mutation_apply_pipeline.py`가 적용한 병합이 잘못 붙었을 때 쓰는
운영 경로다. 저널에 적힌 event id 하나를 지목하면 그 병합이 후보들에게
남긴 자리를 되감고, 원본을 가리키는 되돌림 행을 새로 적는다. 그 행이
있어야 자동 병합이 같은 구성을 다시 붙이지 않는다.

기본은 dry-run이다. 무엇을 되돌릴지만 보여 주고 아무것도 바꾸지 않는다.
실제 되돌림은 --apply를 붙였을 때만 하고, 전체가 한 트랜잭션이다.

개발과 운영 전용이다.

실행:
    uv run python -m catchup.evaluation.rollback_resolution_event \
        --workspace-id 1 --event-id <uuid>
    uv run python -m catchup.evaluation.rollback_resolution_event \
        --workspace-id 1 --event-id <uuid> --operator ops:junsu --apply
"""

from __future__ import annotations

import argparse
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from catchup.configs.config import settings
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)
from catchup.knowledge_maintenance.services.rollback_resolution_event import (
    RollbackError,
)
from catchup.knowledge_maintenance.services.rollback_resolution_event import (
    require_unchanged_since_event,
)
from catchup.knowledge_maintenance.services.rollback_resolution_event import (
    rollback_resolution_event,
)


def _describe(
    uow: KnowledgeMaintenanceUnitOfWork,
    *,
    workspace_id: int,
    event_id: uuid.UUID,
) -> bool:
    """되돌릴 event를 읽어 무엇이 바뀔지 보여 준다.

    아무것도 바꾸지 않는다. commit 없이 나가므로 읽기만 남는다. 실제
    되돌림과 같은 함수로 되돌릴 수 있는지도 미리 물어 본다. 그때 잡는 노드
    잠금은 이 트랜잭션이 끝나면 풀린다.

    Returns:
        되돌릴 수 있는 event면 참을 준다.
    """
    with uow:
        event = uow.resolution_events.get(
            workspace_id=workspace_id,
            event_id=event_id,
        )
        if event is None:
            print(f"event를 찾지 못했다: {event_id}")
            return False
        reversal = uow.resolution_events.find_reversal(
            workspace_id=workspace_id,
            event_id=event_id,
        )
        unchanged_error: RollbackError | None = None
        if event.event_type != "unmerge":
            try:
                require_unchanged_since_event(
                    uow,
                    workspace_id=workspace_id,
                    event=event,
                )
            except RollbackError as error:
                unchanged_error = error

    snapshot = event.member_snapshot
    # 되돌림이 되감는 것은 그 병합이 실제로 옮긴 후보다. 판정 당시 구성인
    # member_candidate_ids에는 적용이 건너뛴 후보도 들어 있다.
    applied = snapshot.get("applied_members")
    member_count = len(applied) if isinstance(applied, list) else 0
    aliases = snapshot.get("aliases_added")
    alias_names = aliases if isinstance(aliases, list) else []

    print("=== 되돌릴 event ===")
    print(f"  id {event.id}")
    print(f"  종류 {event.event_type}  | 결정자 {event.decider}")
    print(f"  노드 {event.node_id}")
    print(f"  이름 {snapshot.get('proposed_name')}")
    print(f"  되돌릴 후보 {member_count}건 (실제로 옮긴 후보)")
    if event.event_type == "merge_into_node":
        print(f"  제거할 별칭 {len(alias_names)}건: {alias_names}")
    else:
        print("  제거할 별칭 없음 (event가 세운 노드를 통째로 물린다)")

    if event.event_type == "unmerge":
        print("되돌림 행은 되돌릴 수 없다.")
        return False
    if reversal is not None:
        print(f"이미 되돌려진 event다: 되돌림 {reversal.id}")
        return False
    if unchanged_error is not None:
        print(f"  되돌릴 수 없음: {unchanged_error}")
        return False
    print("  되돌릴 수 있음 (event 이후 노드에 변화 없음)")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-id", type=int, required=True)
    parser.add_argument("--event-id", type=uuid.UUID, required=True)
    parser.add_argument(
        "--operator",
        default="cli",
        help="되돌림을 결정한 사람을 저널에 남길 이름이다.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="실제로 되돌린다. 없으면 무엇을 되돌릴지만 보여 준다.",
    )
    args = parser.parse_args()

    engine = create_engine(settings.sqlalchemy_database_url)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    uow = KnowledgeMaintenanceUnitOfWork(session_factory)

    try:
        reversible = _describe(
            uow,
            workspace_id=args.workspace_id,
            event_id=args.event_id,
        )
        if not reversible:
            return
        if not args.apply:
            print("dry-run이다. 실제로 되돌리려면 --apply를 붙여라.")
            return

        try:
            result = rollback_resolution_event(
                uow,
                workspace_id=args.workspace_id,
                event_id=args.event_id,
                operator=args.operator,
            )
        except RollbackError as error:
            print(f"되돌리지 못했다: {error}")
            return

        print("=== 되돌림 결과 ===")
        print(f"  되돌림 event {result.unmerge_event_id}")
        print(f"  새 노드 {len(result.new_node_ids)}건")
        for node_id in result.new_node_ids:
            print(f"    - {node_id}")
        print(f"  재배치 후보 {len(result.repointed_candidate_ids)}건")
        print(f"  제거한 별칭 {len(result.removed_aliases)}건")
        for alias in result.removed_aliases:
            print(f"    - {alias}")
        print(
            "  안내: retire된 노드로 편찬된 문서는 남는다. "
            "문서 정리는 별도 처리다."
        )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
