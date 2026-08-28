"""어휘 수렴의 기계 가드·버전·병합 순수 함수를 검증한다."""

from __future__ import annotations

import pytest
from structlog.testing import capture_logs

from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary
from catchup.knowledge_maintenance.contracts.extraction import PredicateEntry
from catchup.knowledge_maintenance.contracts.vocabulary_convergence import (
    PredicateUsage,
)
from catchup.knowledge_maintenance.contracts.vocabulary_convergence import (
    ProposedPredicateEntry,
)
from catchup.knowledge_maintenance.contracts.vocabulary_convergence import (
    ProposedRelationEntry,
)
from catchup.knowledge_maintenance.contracts.vocabulary_convergence import RelationUsage
from catchup.knowledge_maintenance.contracts.vocabulary_convergence import (
    SynonymAbsorption,
)
from catchup.knowledge_maintenance.contracts.vocabulary_convergence import (
    VocabularyConvergenceProposal,
)
from catchup.knowledge_maintenance.services.converge_vocabulary import (
    ConvergenceGuardResult,
)
from catchup.knowledge_maintenance.services.converge_vocabulary import guard_convergence
from catchup.knowledge_maintenance.services.converge_vocabulary import merge_vocabulary
from catchup.knowledge_maintenance.services.converge_vocabulary import (
    next_published_version,
)
from catchup.knowledge_maintenance.services.converge_vocabulary import (
    normalize_vocabulary_name,
)
from catchup.knowledge_maintenance.services.converge_vocabulary import (
    publish_converged_vocabulary,
)
from catchup.knowledge_maintenance.services.converge_vocabulary import (
    resolve_latest_published_version,
)


def _usage(name: str, **overrides) -> PredicateUsage:
    defaults = dict(
        name=name,
        usage_count=2,
        value_types=("date",),
        observed_values=("2026-08-12",),
        example_statements=("예문",),
        subject_types=("service",),
    )
    defaults.update(overrides)
    return PredicateUsage(**defaults)


def _current() -> ExtractionVocabulary:
    return ExtractionVocabulary(
        snapshot_id="v1",
        predicate_entries=(
            PredicateEntry(
                name="deployment_scheduled_on",
                definition="배포 예정일",
                value_type="date",
            ),
        ),
    )


def _proposed(name: str, **overrides) -> ProposedPredicateEntry:
    defaults = dict(
        name=name,
        definition="정의",
        value_type="date",
        source_candidates=(name,),
        reason="이유",
    )
    defaults.update(overrides)
    return ProposedPredicateEntry(**defaults)


def _guard(
    proposal: VocabularyConvergenceProposal,
    *,
    current: ExtractionVocabulary | None = None,
    predicate_usage=(),
    relation_usage=(),
):
    return guard_convergence(
        proposal,
        current=_current() if current is None else current,
        predicate_usage=predicate_usage,
        relation_usage=relation_usage,
    )


def test_발행본만_최신으로_고른다():
    versions = ["2", "unversioned", "round-4", "v2", "v10"]
    assert resolve_latest_published_version(versions) == "v10"
    assert resolve_latest_published_version(["2"]) is None


def test_다음_버전은_단조_증가한다():
    versions = ["2", "unversioned", "round-4", "v2", "v10"]
    assert next_published_version(versions) == "v11"
    assert next_published_version([]) == "v1"


def test_snake_case로_정규화한다():
    assert normalize_vocabulary_name("Deployment Date") == "deployment_date"
    assert normalize_vocabulary_name("릴리즈") == ""


def test_기존_이름은_개정_기각():
    proposal = VocabularyConvergenceProposal(
        predicate_entries=(_proposed("deployment_scheduled_on"),),
    )
    result = _guard(
        proposal,
        predicate_usage=(_usage("deployment_scheduled_on"),),
    )
    assert result.predicate_entries == ()
    assert [r.reason for r in result.rejections] == ["기존 엔트리 개정 금지"]


def test_스키마_위반은_항목만_기각():
    proposal = VocabularyConvergenceProposal(
        predicate_entries=(
            _proposed("broken_enum", value_type="enum", enum_values=()),
            _proposed("release_date"),
        ),
    )
    result = _guard(
        proposal,
        predicate_usage=(_usage("broken_enum"), _usage("release_date")),
    )
    assert [e.name for e in result.predicate_entries] == ["release_date"]
    assert [r.name for r in result.rejections] == ["broken_enum"]


def test_스키마와_관측을_동시에_어기면_스키마_사유로_기각():
    # 가드 순서가 브리프 그대로 4(스키마) → 5(관측 증거)여야 한다. 순서가
    # 뒤집히면 사유가 "관측 증거 없음"으로 바뀐다.
    proposal = VocabularyConvergenceProposal(
        predicate_entries=(
            _proposed(
                "broken_and_unobserved",
                value_type="enum",
                enum_values=(),
                source_candidates=("nowhere",),
            ),
        ),
    )
    result = _guard(proposal, predicate_usage=())
    assert result.predicate_entries == ()
    assert len(result.rejections) == 1
    assert result.rejections[0].reason.startswith("스키마 검증 실패")
    assert "enum" in result.rejections[0].reason


def test_스키마로_기각된_첫_항목도_중복_슬롯을_차지한다():
    # 규칙 3은 무조건적이다. 첫 항목이 뒤에서 떨어져도 같은 이름의 다음
    # 항목은 중복으로 기각된다.
    proposal = VocabularyConvergenceProposal(
        predicate_entries=(
            _proposed("release_date", value_type="enum", enum_values=()),
            _proposed("release_date"),
        ),
    )
    result = _guard(proposal, predicate_usage=(_usage("release_date"),))
    assert result.predicate_entries == ()
    reasons = [r.reason for r in result.rejections]
    assert reasons[0].startswith("스키마 검증 실패")
    assert reasons[1] == "제안 내 중복"


def test_관측_증거_없는_항목_기각():
    proposal = VocabularyConvergenceProposal(
        predicate_entries=(
            _proposed("release_date", source_candidates=("릴리즈일자",)),
        ),
    )
    result = _guard(proposal, predicate_usage=(_usage("other_name"),))
    assert result.predicate_entries == ()
    assert [r.reason for r in result.rejections] == ["관측 증거 없음"]


def test_enum_치역이_관측을_못_덮으면_기각():
    proposal = VocabularyConvergenceProposal(
        predicate_entries=(
            _proposed(
                "priority_level",
                value_type="enum",
                enum_values=("high",),
            ),
        ),
    )
    result = _guard(
        proposal,
        predicate_usage=(
            _usage(
                "priority_level",
                value_types=("enum",),
                observed_values=("high", "urgent"),
            ),
        ),
    )
    assert result.predicate_entries == ()
    assert len(result.rejections) == 1
    assert "enum 치역이 관측을 못 덮는다" in result.rejections[0].reason
    assert "urgent" in result.rejections[0].reason


def test_enum_치역이_관측을_덮으면_통과():
    proposal = VocabularyConvergenceProposal(
        predicate_entries=(
            _proposed(
                "priority_level",
                value_type="enum",
                enum_values=("high", "urgent", "low"),
            ),
        ),
    )
    result = _guard(
        proposal,
        predicate_usage=(
            _usage(
                "priority_level",
                value_types=("enum",),
                observed_values=("high", "urgent"),
            ),
        ),
    )
    assert result.rejections == ()
    assert [e.name for e in result.predicate_entries] == ["priority_level"]


def test_제안_내_중복은_뒤가_기각():
    proposal = VocabularyConvergenceProposal(
        predicate_entries=(
            _proposed("Release Date", source_candidates=("release date",)),
            _proposed("release_date", source_candidates=("release date",)),
        ),
    )
    result = _guard(proposal, predicate_usage=(_usage("release date"),))
    assert [e.name for e in result.predicate_entries] == ["release_date"]
    assert [r.reason for r in result.rejections] == ["제안 내 중복"]


def test_흡수는_정본이_사전에_있어야_한다():
    proposal = VocabularyConvergenceProposal(
        absorptions=(
            SynonymAbsorption(
                candidate_name="배포일",
                canonical_name="deployment_scheduled_on",
            ),
            SynonymAbsorption(
                candidate_name="배포일",
                canonical_name="없는_이름",
            ),
        ),
    )
    result = _guard(proposal, predicate_usage=(_usage("배포일"),))
    assert [a.canonical_name for a in result.absorptions] == ["deployment_scheduled_on"]
    assert [r.reason for r in result.rejections] == ["정본이 사전에 없다"]


def test_관측되지_않은_흡수_대상은_기각():
    proposal = VocabularyConvergenceProposal(
        absorptions=(
            SynonymAbsorption(
                candidate_name="배포일",
                canonical_name="deployment_scheduled_on",
            ),
        ),
    )
    result = _guard(proposal, predicate_usage=())
    assert result.absorptions == ()
    assert [r.reason for r in result.rejections] == ["흡수 대상이 관측되지 않았다"]


def test_통과_항목의_이름은_정규화되어_있다():
    proposal = VocabularyConvergenceProposal(
        predicate_entries=(
            _proposed("Release Date", source_candidates=("release date",)),
        ),
    )
    result = _guard(proposal, predicate_usage=(_usage("release date"),))
    assert [e.name for e in result.predicate_entries] == ["release_date"]


def test_통과분이_덮은_이름을_보고한다():
    proposal = VocabularyConvergenceProposal(
        absorptions=(
            SynonymAbsorption(
                candidate_name="배포일",
                canonical_name="deployment_scheduled_on",
            ),
        ),
        predicate_entries=(
            _proposed(
                "release_date",
                source_candidates=("release date", "ship date"),
            ),
            _proposed("no_evidence", source_candidates=("nowhere",)),
        ),
    )
    result = _guard(
        proposal,
        predicate_usage=(_usage("release date"), _usage("배포일")),
    )
    covered = set(result.covered_names)
    assert "release_date" in covered
    assert "release date" in covered
    assert "ship date" in covered
    assert "배포일" in covered
    assert "no_evidence" not in covered
    assert "nowhere" not in covered


def test_관계_항목도_같은_가드를_받는다():
    proposal = VocabularyConvergenceProposal(
        relation_entries=(
            ProposedRelationEntry(
                name="Depends On",
                definition="의존한다",
                source_candidates=("depends on",),
            ),
            ProposedRelationEntry(
                name="unobserved",
                definition="관측 없음",
            ),
        ),
    )
    result = _guard(
        proposal,
        relation_usage=(RelationUsage(name="depends on", usage_count=3),),
    )
    assert [e.name for e in result.relation_entries] == ["depends_on"]
    assert [r.reason for r in result.rejections] == ["관측 증거 없음"]


def test_병합은_기존을_보존하고_신규를_더한다():
    current = _current()
    proposal = VocabularyConvergenceProposal(
        predicate_entries=(_proposed("release_date"),),
        relation_entries=(
            ProposedRelationEntry(
                name="depends_on",
                definition="의존한다",
                source_candidates=("depends_on",),
            ),
        ),
    )
    guarded = _guard(
        proposal,
        current=current,
        predicate_usage=(_usage("release_date"),),
        relation_usage=(RelationUsage(name="depends_on", usage_count=1),),
    )
    merged = merge_vocabulary(current, guarded, version="v2")
    assert merged.snapshot_id == "v2"
    assert merged.predicates == ("deployment_scheduled_on", "release_date")
    assert merged.relation_types == ("depends_on",)
    assert merged.predicate_entries[0] is current.predicate_entries[0]
    assert len(merged.predicate_entries) == 2


def test_판정_사유가_감사_로그에_남는다():
    # 흡수·채택·기각의 사유는 감사 기록이다. 러너 stdout은 남지 않으므로
    # structlog에 실려야 한다.
    proposal = VocabularyConvergenceProposal(
        absorptions=(
            SynonymAbsorption(
                candidate_name="배포일",
                canonical_name="deployment_scheduled_on",
                reason="같은 날짜를 가리킨다.",
            ),
        ),
        predicate_entries=(
            _proposed("release_date", reason="관측이 날짜로 닫힌다."),
            _proposed("no_evidence", source_candidates=("nowhere",)),
        ),
        relation_entries=(
            ProposedRelationEntry(
                name="depends_on",
                definition="의존한다",
                source_candidates=("depends on",),
                reason="예시가 의존을 말한다.",
            ),
        ),
    )

    with capture_logs() as logs:
        result = _guard(
            proposal,
            predicate_usage=(_usage("release_date"), _usage("배포일")),
            relation_usage=(RelationUsage(name="depends on", usage_count=2),),
        )

    assert len(result.rejections) == 1

    absorptions = [log for log in logs if log["event"] == "vocabulary_absorption_judged"]
    assert absorptions == [
        {
            "event": "vocabulary_absorption_judged",
            "log_level": "info",
            "candidate_name": "배포일",
            "canonical_name": "deployment_scheduled_on",
            "reason": "같은 날짜를 가리킨다.",
        }
    ]

    accepted = {
        log["name"]: log for log in logs if log["event"] == "vocabulary_entry_accepted"
    }
    assert set(accepted) == {"release_date", "depends_on"}
    assert accepted["release_date"]["kind"] == "predicate"
    assert accepted["release_date"]["value_type"] == "date"
    assert accepted["release_date"]["reason"] == "관측이 날짜로 닫힌다."
    assert accepted["depends_on"]["kind"] == "relation"
    assert accepted["depends_on"]["reason"] == "예시가 의존을 말한다."

    rejected = [log for log in logs if log["event"] == "vocabulary_entry_rejected"]
    assert [(log["name"], log["reason"]) for log in rejected] == [
        ("no_evidence", "관측 증거 없음")
    ]

    # 예문·관측값은 상담 원문 조각이라 실리지 않는다.
    assert not any("예문" in str(log) for log in logs)


def test_이름_온리_현행_사전과도_병합된다():
    current = ExtractionVocabulary(snapshot_id="v1", predicates=("legacy_p",))
    proposal = VocabularyConvergenceProposal(
        predicate_entries=(_proposed("release_date"),),
    )
    guarded = _guard(
        proposal,
        current=current,
        predicate_usage=(_usage("release_date"),),
    )
    merged = merge_vocabulary(current, guarded, version="v2")
    assert merged.predicates == ("legacy_p", "release_date")
    assert [e.name for e in merged.predicate_entries] == ["release_date"]


class _FakeOntology:
    """버전 목록과 저장만 흉내 내는 대역이다. 호출 순서를 기록한다."""

    def __init__(self, versions: tuple[str, ...] = ()) -> None:
        self.versions = versions
        self.calls: list[str] = []
        self.published: list[ExtractionVocabulary] = []

    def lock_lineage(self, *, workspace_id: int, ontology_id: str) -> None:
        self.calls.append("lock_lineage")

    def list_versions(
        self,
        *,
        workspace_id: int,
        ontology_id: str,
    ) -> tuple[str, ...]:
        self.calls.append("list_versions")
        return self.versions

    def ensure(
        self,
        *,
        workspace_id: int,
        ontology_id: str,
        vocabulary: ExtractionVocabulary,
    ) -> ExtractionVocabulary:
        self.calls.append("ensure")
        self.published.append(vocabulary)
        return vocabulary


class _FakeUow:
    """`with` 블록과 commit만 세는 최소 UoW 대역이다."""

    def __init__(self, ontology: _FakeOntology) -> None:
        self.ontology = ontology
        self.commits = 0

    def __enter__(self) -> _FakeUow:
        return self

    def __exit__(self, *exc_info) -> None:
        return None

    def commit(self) -> None:
        self.commits += 1


def _publish_guard() -> ConvergenceGuardResult:
    """predicate 하나를 통과시킨 가드 결과를 만든다."""
    return ConvergenceGuardResult(
        predicate_entries=(
            PredicateEntry(
                name="release_channel",
                definition="배포 채널을 담는다.",
                value_type="text",
            ),
        ),
        relation_entries=(),
        absorptions=(),
        rejections=(),
        covered_names=("release_channel",),
    )


def test_빈_기준은_그_사이_발행본이_생겼으면_거부한다():
    # 기준을 읽을 땐 발행본이 없었는데 지금 v1이 보인다면, 그 사이 다른
    # 쪽이 계보를 열었다는 뜻이다. 그대로 쌓으면 v1의 항목이 사라진다.
    uow = _FakeUow(_FakeOntology(versions=("v1",)))

    with pytest.raises(RuntimeError, match="발행본이 없었는데"):
        publish_converged_vocabulary(
            _publish_guard(),
            workspace_id=1,
            ontology_id="catchup.test",
            current=ExtractionVocabulary(),
            uow=uow,
        )

    assert uow.ontology.published == []
    assert uow.commits == 0


def test_빈_기준은_발행본이_없으면_v1을_발행한다():
    uow = _FakeUow(_FakeOntology())

    outcome = publish_converged_vocabulary(
        _publish_guard(),
        workspace_id=1,
        ontology_id="catchup.test",
        current=ExtractionVocabulary(),
        uow=uow,
    )

    assert outcome.version == "v1"
    assert uow.ontology.published[0].predicates == ("release_channel",)
    assert uow.commits == 1


def test_버전_목록을_읽기_전에_계보를_잠근다():
    # 읽은 뒤에 잠그면 이미 남을 본 뒤라 같은 다음 번호를 세는 것을 막지
    # 못한다. 순서가 이 잠금의 전부다.
    uow = _FakeUow(_FakeOntology())

    publish_converged_vocabulary(
        _publish_guard(),
        workspace_id=1,
        ontology_id="catchup.test",
        current=ExtractionVocabulary(),
        uow=uow,
    )

    assert uow.ontology.calls[:2] == ["lock_lineage", "list_versions"]
