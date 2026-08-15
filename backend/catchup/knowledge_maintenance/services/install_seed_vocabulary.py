"""도메인 seed 어휘를 workspace의 현행 어휘에 합쳐 발행한다.

온보딩은 어휘가 이미 있는 workspace에서도 돌 수 있다. 그래서 seed를
덮어쓰지 않고 합집합으로 더한다. 이름이 겹치면 기존 항목이 이긴다 —
사전은 단조 증가하며, 기존 엔트리 개정은 재추출 계약을 바꾸는 일이라
자동으로 하지 않는다.

같은 seed를 두 번 깔아도 두 번째는 아무것도 더하지 않는다. 내용이 같은
버전만 늘면 계보가 무엇이 달라졌는지 말해주지 못하므로, 더할 것이 없으면
발행 자체를 하지 않는다.
"""

from __future__ import annotations

from collections.abc import Iterable
from collections.abc import Sequence
from typing import Protocol
from typing import TypeVar

from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary
from catchup.knowledge_maintenance.ports.ontology import OntologyRepository
from catchup.knowledge_maintenance.services.converge_vocabulary import (
    next_published_version,
)
from catchup.knowledge_maintenance.services.converge_vocabulary import (
    resolve_latest_published_version,
)
from catchup.observability.logging import get_logger

logger = get_logger(__name__)

class _NamedEntry(Protocol):
    """사전 항목이 공통으로 갖는 이름만 요구한다."""

    name: str


_Entry = TypeVar("_Entry", bound=_NamedEntry)


class SeedVocabularyUnitOfWork(Protocol):
    """seed 발행이 필요로 하는 저장소만 요구한다.

    트랜잭션 경계를 요구하지 않는다. 온보딩은 채널·정의 INSERT와 같은
    트랜잭션이어야 하므로 경계는 호출자가 쥔다.
    """

    ontology: OntologyRepository


def _added_entries(
    current: Sequence[_Entry],
    seed: Iterable[_Entry],
) -> tuple[_Entry, ...]:
    """현행에 이름이 없는 seed 항목만 순서대로 고른다."""
    known = {entry.name for entry in current}
    added: list[_Entry] = []
    for entry in seed:
        if entry.name in known:
            continue
        known.add(entry.name)
        added.append(entry)
    return tuple(added)


def _extended_names(
    current: Sequence[str],
    added: Sequence[_NamedEntry],
) -> tuple[str, ...]:
    """현행 이름 목록 뒤에 새 항목 이름을 잇는다.

    이미 목록에 있는 이름은 잇지 않는다. entry 없이 이름만 있던 예전
    스냅샷과 이름이 겹치면 같은 이름이 두 번 실릴 수 있다.
    """
    known = set(current)
    appended = [entry.name for entry in added if entry.name not in known]
    return (*current, *appended)


def install_seed_vocabulary(
    uow: SeedVocabularyUnitOfWork,
    *,
    workspace_id: int,
    seed: ExtractionVocabulary,
    ontology_id: str,
) -> str | None:
    """도메인 seed를 현행 어휘에 합집합으로 병합해 발행한다.

    새 버전 이름을 돌려준다. 병합 결과가 현행과 같으면 발행하지 않고
    None을 돌려준다.

    이름이 겹치면 기존 항목이 이긴다. 사전은 단조 증가하며 기존 엔트리
    개정은 재추출 계약을 바꾸는 일이라 자동으로 하지 않는다.

    with 블록도 commit도 여기서 하지 않는다. 온보딩은 채널·정의 INSERT와
    같은 트랜잭션이어야 하므로 경계는 호출자가 쥔다.
    """
    versions = uow.ontology.list_versions(
        workspace_id=workspace_id,
        ontology_id=ontology_id,
    )
    latest = resolve_latest_published_version(versions)
    current = None
    if latest is not None:
        current = uow.ontology.get(
            workspace_id=workspace_id,
            ontology_id=ontology_id,
            version=latest,
        )
    if current is None:
        current = ExtractionVocabulary()

    added_entity_types = _added_entries(
        current.entity_type_entries,
        seed.entity_type_entries,
    )
    added_predicates = _added_entries(
        current.predicate_entries,
        seed.predicate_entries,
    )
    added_relations = _added_entries(
        current.relation_type_entries,
        seed.relation_type_entries,
    )

    if not (added_entity_types or added_predicates or added_relations):
        logger.info(
            "seed_vocabulary_publish_skipped",
            workspace_id=workspace_id,
            ontology_id=ontology_id,
            base_snapshot_id=current.snapshot_id,
        )
        return None

    version = next_published_version(versions)
    # 이름 목록을 항상 명시해서 넘긴다. `ExtractionVocabulary`는 이름
    # 목록이 비었을 때만 entry에서 파생시키므로, entry 없이 이름만 있는
    # 예전 스냅샷을 병합하면 그 이름들이 조용히 사라진다.
    merged = ExtractionVocabulary(
        snapshot_id=version,
        predicates=_extended_names(current.predicates, added_predicates),
        relation_types=_extended_names(
            current.relation_types,
            added_relations,
        ),
        entity_type_entries=(
            *current.entity_type_entries,
            *added_entity_types,
        ),
        predicate_entries=(
            *current.predicate_entries,
            *added_predicates,
        ),
        relation_type_entries=(
            *current.relation_type_entries,
            *added_relations,
        ),
    )
    uow.ontology.ensure(
        workspace_id=workspace_id,
        ontology_id=ontology_id,
        vocabulary=merged,
    )

    logger.info(
        "seed_vocabulary_published",
        workspace_id=workspace_id,
        ontology_id=ontology_id,
        version=version,
        base_snapshot_id=current.snapshot_id,
        added_entity_type_count=len(added_entity_types),
        added_predicate_count=len(added_predicates),
        added_relation_count=len(added_relations),
    )
    return version
