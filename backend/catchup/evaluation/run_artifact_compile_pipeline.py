"""채널에 걸린 정의가 고른 문서를 컴파일해 검토 큐에 올린다.

`run_claim_conflict_pipeline.py`의 다음 단계다. 저쪽이 값이 어긋나는
쌍을 안건으로 남긴다면, 이 스크립트는 그렇게 쌓인 claim과 안건을 카드
한 장으로 늘어놓아 사람이 한눈에 보게 만든다.

무엇을 문서로 만들지는 정의가 정한다. 몇 개를 만들지 고르는 인자는
없다 — 정의가 고른 노드는 전부 대상이며, 그중 일부만 만들면 같은
정의가 실행마다 다른 문서 묶음을 낳는다. 정의 하나만 시험하고 싶으면
`--definition-id`로 정의 목록 쪽을 좁힌다.

블록의 구성에는 LLM을 부르지 않는다. 카드 본문은 이미 저장된 것을 정해진
순서로 옮긴 것뿐이므로, 같은 입력이면 같은 블록이 나온다. 그래서 여러 번
돌려도 안전하다. 내용 지문이 그대로면 아무것도 쓰지 않고 넘긴다.

블록에 얹는 산문만 LLM이 쓴다. 내용 지문이 그대로인 문서는 산문도 부르지
않으므로 재실행 비용은 종전과 같다. `--no-narrate`를 주면 산문 없이
종전대로 컴파일한다.

어휘 사전은 여기서 읽어 넘긴다. 어느 판본으로 카드를 만들었는지가
블록에 남아야 하고, 그 판본을 고르는 일은 실행을 시작하는 쪽의
결정이기 때문이다.

컴파일은 카드를 확정하지 않는다. 올라간 것은 전부 계류 중인 변경안이며,
승인은 `review_artifact_proposals.py`가 맡는다.

종료 코드를 움직이는 것은 접힌 노드뿐이다. 문서를 세울 수 없어 컴파일을
접은 노드가 하나라도 있으면 1로 끝난다 — 그만큼 카드가 비는데 0으로
끝나면 사람도 자동화도 그 실행을 성공으로 기록한다. 정의를 하나도 읽지
못했거나 `--definition-id`가 가리키는 정의가 없는 경우는 그대로 0이다.
아직 정의를 걸어 두지 않았다는 뜻이지 문서가 빠진 실행이 아니다.

정의를 만드는 CLI나 API는 아직 없다. 그래서 정의가 한 줄도 없는
workspace에서는 이 스크립트가 문서를 한 장도 만들지 않는다. 손으로
한 줄 넣어 시작한다 — 아래 INSERT를 그대로 쓰되 채널·사용자 식별자만
자기 것으로 바꾼다.

    INSERT INTO artifact_definitions (
        id, workspace_id, channel_id, kind, purpose,
        selection_spec, created_by
    ) VALUES (
        gen_random_uuid(),
        1,
        '00000000-0000-0000-0000-000000000000',
        'feature_request_card',
        '요청 하나를 카드 한 장으로 본다',
        '{
           "entity_filter": {"entity_types": ["feature_request"]},
           "relation_paths": [
             {"steps": [{"type": "owned_by", "dir": "out"}]}
           ],
           "predicate_sections": ["status", "priority"]
         }'::jsonb,
        1
    );

selection_spec은 세 칸이 전부다. entity_filter.entity_types가 문서를
세울 노드 종류이고, relation_paths는 관계 블록을 만들 걸음(dir은 out·
in·any)이며, predicate_sections는 실을 절과 그 차례다. 셋 다 어휘에
있는 이름이어야 한다 — 없는 이름은 컴파일에서 그 정의만 건너뛰게
만든다. predicate_sections를 null로 두면 "고르지 않았다"는 뜻이라 모든
절이 어휘가 정한 차례로 실리고, 빈 배열은 "하나도 싣지 않는다"는 뜻이라
claim 절이 없는 문서가 된다. 채널 하나에 같은 kind의 정의는 하나뿐이다.

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

from catchup.components.llm.constants import LlmProvider
from catchup.components.llm.constants import ModelCapacity
from catchup.components.llm.factory import get_llm_service
from catchup.configs.config import settings
from catchup.evaluation.review_artifact_proposals import render_proposal_card
from catchup.knowledge_maintenance.adapters.llm.block_narrator import LlmBlockNarrator
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
    """정의 하나만 보이도록 가린 정의 저장소다.

    가리는 것은 정의 목록뿐이고, 포트의 나머지 조회는 그대로 감싼
    저장소에 넘긴다. 넘기는 자리를 메서드로 적어 둔다 — `__getattr__`로
    받아 넘기면 이 껍데기가 어떤 포트를 채우고 있는지 코드에서 보이지
    않아, 포트에 조회가 늘 때 러너만 조용히 깨진다.
    """

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

    def find_channel_style(self, *, channel_id: uuid.UUID) -> str | None:
        """채널에 걸린 문체 조회는 감싼 저장소에 그대로 넘긴다."""
        return self._inner.find_channel_style(channel_id=channel_id)

    def find_channel_purpose(self, *, channel_id: uuid.UUID) -> str | None:
        """채널에 걸린 목적 조회는 감싼 저장소에 그대로 넘긴다."""
        return self._inner.find_channel_purpose(channel_id=channel_id)


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


def main() -> int:
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
    parser.add_argument(
        "--capacity",
        choices=[capacity.value for capacity in ModelCapacity],
        default=None,
        help=(
            "산문을 쓸 모델 등급이다. 기본은 large다. --no-narrate와 "
            "함께 주면 부를 모델이 없으므로 무시한다."
        ),
    )
    parser.add_argument(
        "--no-narrate",
        action="store_true",
        help=(
            "산문 없이 컴파일한다. 블록 구성만 확인하고 싶을 때 쓴다."
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
        return 0

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
        return 0
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

    capacity = args.capacity or ModelCapacity.LARGE.value
    narrator = None
    if args.no_narrate:
        if args.capacity is not None:
            print(
                "--no-narrate라 산문을 쓰지 않는다. "
                f"--capacity {args.capacity}는 무시한다."
            )
    else:
        service = get_llm_service(
            provider=LlmProvider.AWS_BEDROCK,
            model_capacity=ModelCapacity(capacity),
            streaming=False,
            read_timeout=120,
        )
        narrator = LlmBlockNarrator(service.get_llm())
        print(f"산문 모델 등급 {capacity} 주입")

    result = compile_definition_artifacts(
        uow
        if args.definition_id is None
        else only_definition(uow, args.definition_id),
        workspace_id=args.workspace_id,
        vocabulary=vocabulary,
        narrator=narrator,
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
    # 산문을 새로 받은 블록과 지난 문장을 그대로 다시 쓴 블록 수다.
    # 재사용이 큰 실행일수록 검수자가 볼 산문 diff가 작다.
    print(
        f"  산문 서술 {result.blocks_narrated}"
        f" · 재사용 {result.blocks_narrative_reused}"
    )
    # 문서를 세울 수 없어 컴파일을 접은 노드 수다. 그만큼 카드가 비므로
    # 실행 전체를 실패로 끝낸다.
    print(f"  실패 노드 {result.nodes_failed}")

    _print_pending_cards(uow)

    engine.dispose()
    if result.nodes_failed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
