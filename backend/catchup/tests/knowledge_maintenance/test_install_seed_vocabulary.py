"""seed 어휘 병합 발행의 병합 규칙과 발행 판단을 확인한다.

저장소는 대역으로 둔다. 여기서 볼 것은 무엇을 더하고 무엇을 안 더하는지,
그리고 어느 버전으로 발행하는지이지 SQL이 아니다. 실 저장소 왕복은
`test_install_seed_vocabulary_pg.py`가 맡는다.
"""

from __future__ import annotations

import pytest

from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary
from catchup.knowledge_maintenance.contracts.extraction import PredicateEntry
from catchup.knowledge_maintenance.domain.preset_catalog import _VOC_SEED
from catchup.knowledge_maintenance.ports.ontology import OntologySnapshotConflict
from catchup.knowledge_maintenance.services.install_seed_vocabulary import (
    install_seed_vocabulary,
)

ONTOLOGY_ID = "catchup.test"


class _FakeOntology:
    """버전별 어휘만 흉내 내는 fake다. 같은 버전 다른 내용은 거부한다.

    `hidden_versions`에 넣은 버전은 저장돼 있으면서도 `list_versions`에
    나오지 않는다. 목록을 읽은 뒤 다른 트랜잭션이 같은 버전을 먼저 넣은
    상황을 이 대역으로 재현한다.
    """

    def __init__(self, hidden_versions: frozenset[str] = frozenset()) -> None:
        self.stored: dict[tuple[int, str], ExtractionVocabulary] = {}
        self.hidden_versions = hidden_versions

    def get(
        self,
        *,
        workspace_id: int,
        ontology_id: str,
        version: str,
    ) -> ExtractionVocabulary | None:
        return self.stored.get((workspace_id, version))

    def list_versions(
        self,
        *,
        workspace_id: int,
        ontology_id: str,
    ) -> tuple[str, ...]:
        return tuple(
            version
            for (found_id, version) in self.stored
            if found_id == workspace_id and version not in self.hidden_versions
        )

    def ensure(
        self,
        *,
        workspace_id: int,
        ontology_id: str,
        vocabulary: ExtractionVocabulary,
    ) -> ExtractionVocabulary:
        key = (workspace_id, vocabulary.snapshot_id)
        found = self.stored.get(key)
        if found is not None:
            if found != vocabulary:
                raise OntologySnapshotConflict("다른 어휘다")
            return found
        self.stored[key] = vocabulary
        return vocabulary


class _FakeUow:
    """`ontology` 하나만 가진 최소 UoW 대역이다."""

    def __init__(self, ontology: _FakeOntology) -> None:
        self.ontology = ontology


def test_publishes_v1_on_an_empty_workspace() -> None:
    """어휘가 없던 workspace에는 v1으로 발행한다."""
    uow = _FakeUow(_FakeOntology())

    version = install_seed_vocabulary(
        uow,
        workspace_id=1,
        seed=_VOC_SEED,
        ontology_id=ONTOLOGY_ID,
    )

    assert version == "v1"
    stored = uow.ontology.stored[(1, "v1")]
    assert {entry.name for entry in stored.entity_type_entries} == {
        "feature_request",
        "customer",
        "product_area",
        "complaint_topic",
    }


def test_merges_as_a_union_into_the_next_version() -> None:
    """기존 어휘가 있으면 신규 이름만 더해 v2로 발행한다."""
    ontology = _FakeOntology()
    ontology.stored[(1, "v1")] = ExtractionVocabulary(
        snapshot_id="v1",
        predicate_entries=(
            PredicateEntry(
                name="owner_team",
                definition="담당 팀을 나타낸다.",
                value_type="text",
            ),
        ),
    )

    version = install_seed_vocabulary(
        _FakeUow(ontology),
        workspace_id=1,
        seed=_VOC_SEED,
        ontology_id=ONTOLOGY_ID,
    )

    assert version == "v2"
    merged = ontology.stored[(1, "v2")]
    names = [entry.name for entry in merged.predicate_entries]
    assert names[0] == "owner_team"
    assert "request_status" in names
    assert merged.predicates == tuple(names)


def test_existing_entry_wins_on_a_name_clash() -> None:
    """이름이 겹치면 기존 정의가 그대로 남는다."""
    ontology = _FakeOntology()
    ontology.stored[(1, "v1")] = ExtractionVocabulary(
        snapshot_id="v1",
        predicate_entries=(
            PredicateEntry(
                name="request_status",
                definition="여기서 굳은 뜻이다.",
                value_type="text",
            ),
        ),
    )

    install_seed_vocabulary(
        _FakeUow(ontology),
        workspace_id=1,
        seed=_VOC_SEED,
        ontology_id=ONTOLOGY_ID,
    )

    merged = ontology.stored[(1, "v2")]
    kept = merged.predicate_entry("request_status")
    assert kept.definition == "여기서 굳은 뜻이다."
    assert kept.value_type == "text"
    assert [
        entry.name for entry in merged.predicate_entries
    ].count("request_status") == 1


def test_keeps_names_of_an_entryless_snapshot() -> None:
    """entry 없이 이름만 있던 스냅샷의 이름이 사라지지 않는다."""
    ontology = _FakeOntology()
    ontology.stored[(1, "v1")] = ExtractionVocabulary(
        snapshot_id="v1",
        predicates=("legacy_status", "request_status"),
        relation_types=("legacy_link",),
    )

    install_seed_vocabulary(
        _FakeUow(ontology),
        workspace_id=1,
        seed=_VOC_SEED,
        ontology_id=ONTOLOGY_ID,
    )

    merged = ontology.stored[(1, "v2")]
    assert merged.predicates[0] == "legacy_status"
    assert merged.relation_types[0] == "legacy_link"
    assert merged.predicates.count("request_status") == 1
    assert "requested_by" in merged.relation_types


def test_second_install_of_the_same_seed_publishes_nothing() -> None:
    """같은 seed를 두 번 깔면 두 번째는 발행하지 않는다."""
    uow = _FakeUow(_FakeOntology())

    install_seed_vocabulary(
        uow,
        workspace_id=1,
        seed=_VOC_SEED,
        ontology_id=ONTOLOGY_ID,
    )
    again = install_seed_vocabulary(
        uow,
        workspace_id=1,
        seed=_VOC_SEED,
        ontology_id=ONTOLOGY_ID,
    )

    assert again is None
    assert list(uow.ontology.stored) == [(1, "v1")]


def test_empty_seed_publishes_nothing() -> None:
    """더할 것이 없는 seed는 빈 workspace에서도 발행하지 않는다."""
    uow = _FakeUow(_FakeOntology())

    version = install_seed_vocabulary(
        uow,
        workspace_id=1,
        seed=ExtractionVocabulary(),
        ontology_id=ONTOLOGY_ID,
    )

    assert version is None
    assert uow.ontology.stored == {}


def test_keeps_the_vn_lineage_past_v9() -> None:
    """버전 계산은 사전순이 아니라 숫자순이다."""
    ontology = _FakeOntology()
    ontology.stored[(1, "v9")] = ExtractionVocabulary(snapshot_id="v9")

    version = install_seed_vocabulary(
        _FakeUow(ontology),
        workspace_id=1,
        seed=_VOC_SEED,
        ontology_id=ONTOLOGY_ID,
    )

    assert version == "v10"


def test_conflict_from_ensure_propagates() -> None:
    """같은 버전에 다른 내용이 있으면 그대로 터진다."""
    ontology = _FakeOntology(hidden_versions=frozenset({"v2"}))
    ontology.stored[(1, "v1")] = ExtractionVocabulary(
        snapshot_id="v1",
        predicate_entries=(
            PredicateEntry(name="x", definition="설명이다.", value_type="text"),
        ),
    )
    ontology.stored[(1, "v2")] = ExtractionVocabulary(snapshot_id="v2")

    with pytest.raises(OntologySnapshotConflict):
        install_seed_vocabulary(
            _FakeUow(ontology),
            workspace_id=1,
            seed=_VOC_SEED,
            ontology_id=ONTOLOGY_ID,
        )


def test_other_workspace_vocabulary_is_untouched() -> None:
    """다른 workspace의 어휘는 기준에도 결과에도 끼지 않는다."""
    ontology = _FakeOntology()
    ontology.stored[(2, "v1")] = ExtractionVocabulary(snapshot_id="v1")

    version = install_seed_vocabulary(
        _FakeUow(ontology),
        workspace_id=1,
        seed=_VOC_SEED,
        ontology_id=ONTOLOGY_ID,
    )

    assert version == "v1"
    assert (1, "v1") in ontology.stored
    assert ontology.stored[(2, "v1")].predicate_entries == ()
