"""채널에 걸린 정의가 고른 문서를 컴파일해 검토 큐에 올린다.

`run_claim_conflict_pipeline.py`의 다음 단계다. 저쪽이 값이 어긋나는
쌍을 안건으로 남긴다면, 이 스크립트는 그렇게 쌓인 claim과 안건을 카드
한 장으로 늘어놓아 사람이 한눈에 보게 만든다.

무엇을 문서로 만들지는 정의가 정한다. 몇 개를 만들지 고르는 인자는
없다 — 정의가 고른 노드는 전부 대상이며, 그중 일부만 만들면 같은
정의가 실행마다 다른 문서 묶음을 낳는다. 정의 하나만 시험하고 싶으면
`--definition-id`로 정의 목록 쪽을 좁힌다.

LLM을 부르지 않는다. 카드 본문은 이미 저장된 것을 정해진 순서로 옮긴
것뿐이므로, 같은 입력이면 같은 본문이 나온다. 그래서 여러 번 돌려도
안전하다. 내용 지문이 그대로면 아무것도 쓰지 않고 넘긴다.

어휘 사전은 여기서 읽어 넘긴다. 어느 판본으로 카드를 만들었는지가
블록에 남아야 하고, 그 판본을 고르는 일은 실행을 시작하는 쪽의
결정이기 때문이다.

컴파일은 카드를 확정하지 않는다. 올라간 것은 전부 계류 중인 변경안이며,
승인은 `review_artifact_proposals.py`가 맡는다.

개발과 평가 전용이다.

실행:
    uv run python -m catchup.evaluation.run_artifact_compile_pipeline
    uv run python -m catchup.evaluation.run_artifact_compile_pipeline \
        --workspace-id 1 --definition-id 0a1b2c3d-...
"""

from __future__ import annotations

import argparse
import uuid
from types import TracebackType
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from catchup.configs.config import settings
from catchup.evaluation.review_artifact_proposals import render_proposal_card
from catchup.knowledge_maintenance.adapters.llm.structured_extractor import CONTRACT_ID
from catchup.knowledge_maintenance.adapters.postgres.unit_of_work import (
    KnowledgeMaintenanceUnitOfWork,
)
from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary
from catchup.knowledge_maintenance.ports.artifact_definitions import (
    ArtifactDefinitionRepository,
)
from catchup.knowledge_maintenance.ports.artifact_definitions import (
    StoredArtifactDefinition,
)
from catchup.knowledge_maintenance.services.compile_entity_artifacts import (
    compile_definition_artifacts,
)
from catchup.knowledge_maintenance.services.converge_vocabulary import (
    resolve_latest_published_version,
)


class _SingleDefinitionRepository:
    """정의 하나만 보이도록 가린 정의 저장소다."""

    def __init__(
        self,
        inner: ArtifactDefinitionRepository,
        definition_id: uuid.UUID,
    ) -> None:
        self._inner = inner
        self._definition_id = definition_id

    def list_definitions(self) -> tuple[StoredArtifactDefinition, ...]:
        """고른 정의만 돌려준다. 그런 정의가 없으면 빈 목록이다."""
        return tuple(
            definition
            for definition in self._inner.list_definitions()
            if definition.id == self._definition_id
        )


class _SingleDefinitionUnitOfWork:
    """정의 목록만 가려 넘기는 UnitOfWork 껍데기다.

    거르는 자리를 러너에 둔다. 컴파일 서비스의 계약은 "workspace의 정의를
    전부 돈다"이므로, 몇 개만 돌라는 인자를 서비스에 두면 러너의 편의가
    컴파일 규칙이 된다.

    정의 저장소는 그때그때 감싼다. 실제 UnitOfWork는 저장소를 `__enter__`
    에서 만들므로, 만들기 전에 붙들면 지난 실행의 저장소를 잡는다.
    """

    def __init__(
        self,
        inner: KnowledgeMaintenanceUnitOfWork,
        definition_id: uuid.UUID,
    ) -> None:
        self._inner = inner
        self._definition_id = definition_id

    @property
    def artifact_definitions(self) -> _SingleDefinitionRepository:
        """가려 둔 정의 저장소를 돌려준다."""
        return _SingleDefinitionRepository(
            self._inner.artifact_definitions, self._definition_id
        )

    def __getattr__(self, name: str) -> Any:
        """정의 말고는 감싼 UnitOfWork의 것을 그대로 쓴다."""
        return getattr(self._inner, name)

    def __enter__(self) -> _SingleDefinitionUnitOfWork:
        self._inner.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._inner.__exit__(exc_type, exc_value, traceback)

    def commit(self) -> None:
        self._inner.commit()


def only_definition(
    uow: KnowledgeMaintenanceUnitOfWork,
    definition_id: uuid.UUID,
) -> _SingleDefinitionUnitOfWork:
    """정의 하나만 보이는 UnitOfWork로 감싼다."""
    return _SingleDefinitionUnitOfWork(uow, definition_id)


def _load_vocabulary(
    uow: KnowledgeMaintenanceUnitOfWork,
    *,
    workspace_id: int,
    version: str,
) -> ExtractionVocabulary | None:
    """카드에 판본으로 남길 어휘 스냅샷을 읽는다."""
    with uow:
        return uow.ontology.get(
            workspace_id=workspace_id,
            ontology_id=CONTRACT_ID,
            version=version,
        )


def _print_pending_cards(uow: KnowledgeMaintenanceUnitOfWork) -> None:
    """지금 검토를 기다리는 카드를 전부 펼쳐 보여 준다.

    컴파일 결과는 어느 변경안이 이번에 올라갔는지를 돌려주지 않는다.
    그래서 이번 실행분만 골라내지 않고 계류 큐 전체를 보여 준다. 지난
    실행이 남긴 것도 아직 사람이 봐야 할 카드라는 점에서는 같다.
    """
    with uow:
        pending = uow.artifacts.list_pending_proposals()

    if not pending:
        print("검토를 기다리는 카드가 없다.")
        return

    print(f"=== 계류 중인 카드 {len(pending)}건 (지난 실행분 포함) ===")
    for proposal in pending:
        print()
        print(render_proposal_card(proposal))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-id", type=int, default=1)
    parser.add_argument(
        "--definition-id",
        type=uuid.UUID,
        default=None,
        help=(
            "이 정의 하나만 컴파일한다. 생략하면 workspace의 정의를 모두 "
            "돈다."
        ),
    )
    parser.add_argument(
        "--ontology-version",
        default=None,
        help=(
            "카드에 판본으로 남길 어휘 스냅샷 버전. 생략하면 최신 발행본을 "
            "고른다."
        ),
    )
    args = parser.parse_args()

    engine = create_engine(settings.sqlalchemy_database_url)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    uow = KnowledgeMaintenanceUnitOfWork(
        session_factory,
        workspace_id=args.workspace_id,
    )

    version = args.ontology_version
    if version is None:
        with uow:
            version = resolve_latest_published_version(
                uow.ontology.list_versions(
                    workspace_id=args.workspace_id,
                    ontology_id=CONTRACT_ID,
                )
            )
    if version is None:
        print(
            "발행된 어휘 스냅샷이 없다. "
            "run_vocabulary_convergence_pipeline을 먼저 돌린다."
        )
        engine.dispose()
        return

    vocabulary = _load_vocabulary(
        uow,
        workspace_id=args.workspace_id,
        version=version,
    )
    if vocabulary is None:
        print(
            f"어휘 스냅샷 {version}이 없다. "
            f"run_vocabulary_convergence_pipeline을 먼저 돌린다."
        )
        engine.dispose()
        return
    if not vocabulary.predicate_entries:
        # 사전이 비면 카드는 만들어지지만 predicate 순서를 사람이 정한
        # 대로 놓지 못하고 이름순으로 떨어진다. 그 사실을 미리 알린다.
        print(
            f"어휘 스냅샷 {version}에 predicate 사전 항목이 "
            f"없다. 카드의 절 순서는 이름순으로 떨어진다."
        )
    else:
        print(
            f"어휘 스냅샷 {vocabulary.snapshot_id} predicate 사전 "
            f"{len(vocabulary.predicate_entries)}종 주입"
        )

    result = compile_definition_artifacts(
        uow
        if args.definition_id is None
        else only_definition(uow, args.definition_id),
        workspace_id=args.workspace_id,
        vocabulary=vocabulary,
    )

    print("=== 정의 기반 문서 컴파일 결과 ===")
    if result.definitions_considered == 0:
        # 정의가 없으면 문서도 없다. 조용히 0으로 끝나면 컴파일이 돈
        # 것처럼 보이므로 무엇이 빠졌는지 적는다.
        print(
            "  읽은 정의가 없다. 채널에 정의를 걸어야 문서가 만들어진다."
        )
    print(f"  읽은 정의 {result.definitions_considered}")
    print(f"  대상 노드 {result.nodes_considered}")
    # 서비스 필드 이름과 달리 뜻은 "처음 올림"과 "직전 계류를 대신해
    # 다시 올림"이다. 이름을 그대로 적으면 되살아난 행으로 읽히므로
    # 여기서는 뜻으로 적는다. "충돌 보류"는 승인된 옛 판 내용으로
    # 되돌아가 멱등 키가 부딪혀 이번에 올리지 못한 문서 수다.
    print(
        f"  변경안 신규 {result.proposals_created}"
        f" · 갱신 {result.proposals_revived}"
        f" · 접힘 {result.proposals_abandoned}"
        f" · 내용 그대로 {result.unchanged_skipped}"
        f" · 충돌 보류 {result.proposals_conflicted}"
    )
    # 반려된 내용과 지문이 같아 카드에서 빠진 블록 수다. 조용히 사라지면
    # 카드가 왜 짧아졌는지 알 길이 없으므로 함께 적는다.
    print(f"  반려 재등장 차단 블록 {result.blocks_suppressed}")

    _print_pending_cards(uow)

    engine.dispose()


if __name__ == "__main__":
    main()
