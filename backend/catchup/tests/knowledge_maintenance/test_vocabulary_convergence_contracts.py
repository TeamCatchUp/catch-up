from __future__ import annotations

import pytest
from pydantic import ValidationError

from catchup.knowledge_maintenance.contracts.vocabulary_convergence import (
    PredicateUsage,
)
from catchup.knowledge_maintenance.contracts.vocabulary_convergence import (
    ProposedPredicateEntry,
)
from catchup.knowledge_maintenance.contracts.vocabulary_convergence import (
    VocabularyConvergenceProposal,
)


class TestPredicateUsage:
    def test_필드를_보존한다(self) -> None:
        usage = PredicateUsage(
            name="deployment_scheduled_on",
            usage_count=3,
            value_types=("date",),
            observed_values=("2026-08-12", "2026-08-13"),
            example_statements=("배포는 수요일로 예정되어 있다",),
            subject_types=("service",),
        )
        assert usage.usage_count == 3
        assert usage.observed_values == ("2026-08-12", "2026-08-13")

    def test_불변이다(self) -> None:
        usage = PredicateUsage(name="p", usage_count=1)
        with pytest.raises(ValidationError):
            usage.name = "other"


class TestVocabularyConvergenceProposal:
    def test_enum인데_치역이_없어도_파싱은_통과한다(self) -> None:
        # 항목별 결함은 가드가 기각한다. 여기서 막으면 항목 하나가
        # 전체 LLM 출력 파싱을 무너뜨린다.
        proposal = VocabularyConvergenceProposal(
            predicate_entries=(
                ProposedPredicateEntry(
                    name="deployment_status",
                    definition="배포 진행 상태",
                    value_type="enum",
                    enum_values=(),
                    source_candidates=("deploy_state",),
                    reason="동의어 병합",
                ),
            ),
        )
        assert proposal.predicate_entries[0].value_type == "enum"

    def test_빈_제안이_기본값이다(self) -> None:
        proposal = VocabularyConvergenceProposal()
        assert proposal.absorptions == ()
        assert proposal.predicate_entries == ()
        assert proposal.relation_entries == ()
