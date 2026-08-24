"""워크스페이스 하나의 LLM 위키·knowledge_maintenance 데이터를 초기화한다.

debug 엔드포인트(catchup/server/debug/knowledge_maintenance_reset.py)는
TRUNCATE라서 모든 워크스페이스를 함께 비우고, 위키 아티팩트·해소·리뷰
테이블이 목록에 없다. 이 스크립트는 workspace_id로 좁혀서 지우고,
파이프라인 이후에 생긴 테이블까지 포함한다.

기본은 dry-run이라 지울 행 수만 세어 보여 준다. 실제 삭제는 --yes를
붙였을 때만 하고, 전체가 한 트랜잭션이라 중간에 실패하면 아무것도
지워지지 않는다.

선택 옵션:
- --keep-source-versions: 수집 입력(source_versions)은 남긴다.
  observations는 source_versions에 매달려 있으므로 함께 남지 않고
  별도로 지워진다.
- --include-channels: 위키 채널 구조(channels·channel_folders·
  artifact_definitions와 채널에 매달린 역할·목적 행)까지 지운다.
  기본은 콘텐츠만 지우고 구조는 남긴다.
- --include-settings: test_knowledge_maintaince_settings 행도 지운다.

사용 예 (backend/ 에서):
    uv run python scripts/reset_knowledge_maintenance.py --workspace-id 1
    uv run python scripts/reset_knowledge_maintenance.py --workspace-id 1 --yes
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from sqlalchemy.orm import Session

from catchup.db.engine import SessionLocal

# (라벨, SQL) 순서 그대로 지운다. 자식 테이블이 먼저 오도록 FK 역순으로
# 나열했고, SQL은 전부 이 파일의 고정 문자열이라 외부 입력이 섞이지 않는다.
# 모든 문장은 :ws 파라미터 하나만 받는다.

_WS = "workspace_id = :ws"

# 해소·변이 제안: event 저널 → 오퍼레이션 → 제안 → 별칭 → 이름 임베딩 캐시.
# 이 묶음이 스테이징보다 먼저 온다. knowledge_mutation_proposals 와
# knowledge_mutation_operations 는 trigger_entity_candidate_id 처럼 후보 행을
# 가리키는 FK 를 들고 있어서, 후보를 먼저 지우면 FK 위반으로 트랜잭션 전체가
# 되돌아간다. knowledge_node_aliases 는 knowledge_nodes 를 가리키지만 노드는
# 아래 _NODES 에서 지우므로 이 자리에 있어도 된다.
# knowledge_resolution_events 의 reverses_event_id 는 같은 테이블을 가리키는
# 자기참조 FK 지만, PostgreSQL 은 FK 검사를 문장이 끝난 뒤에 하므로 한 DELETE
# 문이 참조하는 행과 참조되는 행을 함께 지운다. 따로 순서를 잡을 필요가 없다.
_RESOLUTION = [
    (
        "knowledge_resolution_events",
        f"DELETE FROM knowledge_resolution_events WHERE {_WS}",
    ),
    (
        "knowledge_mutation_operations",
        f"DELETE FROM knowledge_mutation_operations WHERE {_WS}",
    ),
    (
        "knowledge_mutation_proposals",
        f"DELETE FROM knowledge_mutation_proposals WHERE {_WS}",
    ),
    ("knowledge_node_aliases", f"DELETE FROM knowledge_node_aliases WHERE {_WS}"),
    ("knowledge_name_embeddings", f"DELETE FROM knowledge_name_embeddings WHERE {_WS}"),
]

# 추출 스테이징: 근거 링크 → 주장 후보 → 관계 후보 → 엔티티 후보 →
# 추출 런 → 온톨로지 스냅샷 → 아웃박스.
# 주장 후보와 관계 후보는 둘 다 엔티티 후보를 가리키므로 엔티티 후보보다
# 먼저 지운다. 세 후보 모두 추출 런을 가리키고, 추출 런은 온톨로지 스냅샷을
# 가리킨다. 아웃박스는 다른 테이블과 FK 로 얽혀 있지 않아 어디에 두어도 되고,
# 스테이징의 마지막에 둔다.
_STAGING = [
    (
        "knowledge_candidate_evidence_links",
        f"DELETE FROM knowledge_candidate_evidence_links WHERE {_WS}",
    ),
    (
        "knowledge_claim_candidates",
        f"DELETE FROM knowledge_claim_candidates WHERE {_WS}",
    ),
    (
        "knowledge_relation_assertion_candidates",
        f"DELETE FROM knowledge_relation_assertion_candidates WHERE {_WS}",
    ),
    (
        "knowledge_entity_candidates",
        f"DELETE FROM knowledge_entity_candidates WHERE {_WS}",
    ),
    ("knowledge_extraction_runs", f"DELETE FROM knowledge_extraction_runs WHERE {_WS}"),
    (
        "knowledge_ontology_snapshots",
        f"DELETE FROM knowledge_ontology_snapshots WHERE {_WS}",
    ),
    ("knowledge_pipeline_outbox", f"DELETE FROM knowledge_pipeline_outbox WHERE {_WS}"),
]

# 위키 아티팩트: 판정 → 버전 → 즐겨찾기 → 소유자 → 변경 제안 → 아티팩트.
# artifact_owners에는 workspace_id가 없어서 아티팩트를 거쳐 좁힌다.
# knowledge_artifact_revisions.source_proposal_id 는 변경 제안을 가리키고
# knowledge_artifact_change_proposals.base_revision_id 는 거꾸로 버전을
# 가리켜서 두 테이블이 서로를 참조한다. 어느 쪽을 먼저 지워도 다른 쪽이
# 걸리므로, 삭제 전에 _CYCLE_BREAKS 로 base_revision_id 를 NULL 로 만들어
# 고리를 끊고 나서 버전 → 변경 제안 순으로 지운다.
_ARTIFACTS = [
    ("knowledge_block_verdicts", f"DELETE FROM knowledge_block_verdicts WHERE {_WS}"),
    (
        "knowledge_artifact_revisions",
        f"DELETE FROM knowledge_artifact_revisions WHERE {_WS}",
    ),
    ("wiki_artifact_favorites", f"DELETE FROM wiki_artifact_favorites WHERE {_WS}"),
    (
        "artifact_owners",
        "DELETE FROM artifact_owners WHERE artifact_id IN"
        f" (SELECT id FROM knowledge_artifacts WHERE {_WS})",
    ),
    (
        "knowledge_artifact_change_proposals",
        f"DELETE FROM knowledge_artifact_change_proposals WHERE {_WS}",
    ),
    ("knowledge_artifacts", f"DELETE FROM knowledge_artifacts WHERE {_WS}"),
]

# 캐노니컬 노드와 관측: 노드를 참조하던 자식들이 위에서 다 지워진 뒤에 온다.
_NODES = [
    ("knowledge_nodes", f"DELETE FROM knowledge_nodes WHERE {_WS}"),
    ("observations", f"DELETE FROM observations WHERE {_WS}"),
]

_SOURCE_VERSIONS = [
    ("source_versions", f"DELETE FROM source_versions WHERE {_WS}"),
]

# 채널 구조: 정의 → 채널에 매달린 역할·목적 → 폴더 → 채널.
# channel_admins·channel_purposes에는 workspace_id가 없어서 채널을 거쳐 좁힌다.
_CHANNELS = [
    ("artifact_definitions", f"DELETE FROM artifact_definitions WHERE {_WS}"),
    (
        "channel_admins",
        "DELETE FROM channel_admins WHERE channel_id IN"
        f" (SELECT id FROM channels WHERE {_WS})",
    ),
    (
        "channel_purposes",
        "DELETE FROM channel_purposes WHERE channel_id IN"
        f" (SELECT id FROM channels WHERE {_WS})",
    ),
    ("channel_folders", f"DELETE FROM channel_folders WHERE {_WS}"),
    ("channels", f"DELETE FROM channels WHERE {_WS}"),
]

_SETTINGS = [
    (
        "test_knowledge_maintaince_settings",
        f"DELETE FROM test_knowledge_maintaince_settings WHERE {_WS}",
    ),
]


# 삭제 직전에 실행해서 테이블끼리 서로를 가리키는 고리를 끊는다.
# 지울 행의 열을 NULL 로 바꾸기만 하므로 dry-run 에서는 실행하지 않는다.
_CYCLE_BREAKS = [
    (
        "knowledge_artifact_change_proposals.base_revision_id",
        "UPDATE knowledge_artifact_change_proposals SET base_revision_id = NULL"
        f" WHERE {_WS} AND base_revision_id IS NOT NULL",
    ),
]


def _build_plan(args: argparse.Namespace) -> list[tuple[str, str]]:
    plan = [*_RESOLUTION, *_STAGING, *_ARTIFACTS, *_NODES]
    if not args.keep_source_versions:
        plan += _SOURCE_VERSIONS
    if args.include_channels:
        plan += _CHANNELS
    if args.include_settings:
        plan += _SETTINGS
    return plan


def _count(db: Session, delete_sql: str, workspace_id: int) -> int:
    count_sql = delete_sql.replace("DELETE FROM", "SELECT count(*) FROM", 1)
    return db.execute(text(count_sql), {"ws": workspace_id}).scalar_one()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="워크스페이스 하나의 LLM 위키·knowledge_maintenance 데이터를 지운다.",
    )
    parser.add_argument("--workspace-id", type=int, required=True)
    parser.add_argument(
        "--yes",
        action="store_true",
        help="실제로 삭제한다. 없으면 dry-run으로 행 수만 보여 준다.",
    )
    parser.add_argument(
        "--keep-source-versions",
        action="store_true",
        help="수집 입력(source_versions)은 지우지 않는다.",
    )
    parser.add_argument(
        "--include-channels",
        action="store_true",
        help="위키 채널·폴더·정의 등 구조 테이블까지 지운다.",
    )
    parser.add_argument(
        "--include-settings",
        action="store_true",
        help="test_knowledge_maintaince_settings 행도 지운다.",
    )
    args = parser.parse_args()

    plan = _build_plan(args)

    db = SessionLocal()
    try:
        exists = db.execute(
            text("SELECT 1 FROM workspaces WHERE id = :ws"),
            {"ws": args.workspace_id},
        ).scalar()
        if exists is None:
            print(f"workspace {args.workspace_id} 이(가) 없다.", file=sys.stderr)
            return 1

        counts = {label: _count(db, sql, args.workspace_id) for label, sql in plan}
        total = sum(counts.values())

        mode = "삭제" if args.yes else "dry-run"
        print(f"[{mode}] workspace {args.workspace_id}")
        for label, n in counts.items():
            print(f"  {label:45s} {n:8d}")
        print(f"  {'합계':45s} {total:8d}")

        if not args.yes:
            print("\n행 수만 셌다. 실제로 지우려면 --yes 를 붙인다.")
            return 0

        for _label, sql in _CYCLE_BREAKS:
            db.execute(text(sql), {"ws": args.workspace_id})

        for _label, sql in plan:
            db.execute(text(sql), {"ws": args.workspace_id})
        db.commit()
        print("\n삭제하고 커밋했다.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
