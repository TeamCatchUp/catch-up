"""어휘 자동 수렴의 기계 가드·버전·병합을 정의한다.

사람 검수 대신 기계 가드가 LLM 제안을 받아들일지 판정한다. 가드는 순수
함수다. DB도 LLM도 부르지 않으므로 같은 입력이면 같은 판정이 나오고,
판정 근거를 그대로 감사 기록에 쓸 수 있다.

항목 하나의 기각이 나머지 처리를 멈추지 않는다. LLM 출력은 항목 단위로
결함이 생기므로, 전체 파싱을 무너뜨리는 대신 결함 항목만 떨어뜨린다.

이번 슬라이스의 사전은 단조 증가한다. 기존 엔트리 개정은 재추출 계약을
바꾸는 일이므로 기계가 자동으로 하지 않는다.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from pydantic import ValidationError

from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary
from catchup.knowledge_maintenance.contracts.extraction import PredicateEntry
from catchup.knowledge_maintenance.contracts.extraction import RelationTypeEntry
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

# 발행된 어휘 스냅샷의 이름 체계다. `round-4`처럼 실험용으로 만든 스냅샷은
# 여기 걸리지 않아 최신 발행본 계산에서 빠진다.
PUBLISHED_VERSION_PATTERN = re.compile(r"^v(\d+)$")


def resolve_latest_published_version(
    versions: Sequence[str],
) -> str | None:
    """발행본 체계(`vN`)의 최신 버전을 고른다.

    문자열이 아니라 숫자로 비교한다. 사전순으로 보면 `v10`이 `v9`보다
    작아진다.
    """
    numbers = [
        int(match.group(1))
        for version in versions
        if (match := PUBLISHED_VERSION_PATTERN.match(version))
    ]
    if not numbers:
        return None
    return f"v{max(numbers)}"


def next_published_version(versions: Sequence[str]) -> str:
    """다음 발행 버전 이름을 만든다."""
    latest = resolve_latest_published_version(versions)
    if latest is None:
        return "v1"
    return f"v{int(latest[1:]) + 1}"


def normalize_vocabulary_name(name: str) -> str:
    """어휘 이름을 snake_case로 정규화한다.

    ASCII 소문자·숫자·밑줄만 남긴다. 한글만으로 된 이름은 빈 문자열이
    되어 가드에서 기각된다.
    """
    lowered = name.strip().lower()
    replaced = re.sub(r"[\s\-]+", "_", lowered)
    cleaned = re.sub(r"[^a-z0-9_]", "", replaced)
    collapsed = re.sub(r"_+", "_", cleaned)
    return collapsed.strip("_")


@dataclass(frozen=True, slots=True)
class GuardRejection:
    """기각된 항목의 이름과 첫 위반 사유를 담는다."""

    name: str
    reason: str


@dataclass(frozen=True, slots=True)
class ConvergenceGuardResult:
    """가드를 통과한 것과 기각된 것을 나눠 담는다.

    Attributes:
        predicate_entries: 통과한 predicate 사전 항목을 담는다.
        relation_entries: 통과한 relation 사전 항목을 담는다.
        absorptions: 통과한 동의어 흡수 판정을 담는다.
        rejections: 기각된 항목과 사유를 담는다.
        covered_names: 통과 entry의 이름·source_candidates와 통과
            absorption의 candidate_name을 모은 목록이다. 러너가 잔여
            OOV를 계산하는 근거다.
    """

    predicate_entries: tuple[PredicateEntry, ...]
    relation_entries: tuple[RelationTypeEntry, ...]
    absorptions: tuple[SynonymAbsorption, ...]
    rejections: tuple[GuardRejection, ...]
    covered_names: tuple[str, ...]


def _observed_names(
    usage: Sequence[PredicateUsage] | Sequence[RelationUsage],
    known: Sequence[str],
) -> set[str]:
    """사전 밖에서 관측된 이름 집합을 만든다.

    원본 이름과 정규화형을 모두 담는다. 제안이 어느 쪽 표기로 근거를
    적어도 매칭되게 하려는 것이다.
    """
    known_set = set(known)
    names: set[str] = set()
    for item in usage:
        if item.name in known_set:
            continue
        names.add(item.name)
        names.add(normalize_vocabulary_name(item.name))
    return names


def _summarize_validation_error(error: ValidationError) -> str:
    """검증 오류를 한 줄 사유로 줄인다."""
    parts = []
    for detail in error.errors():
        location = ".".join(str(item) for item in detail["loc"]) or "model"
        parts.append(f"{location}: {detail['msg']}")
    return "; ".join(parts)


def _matched_usage(
    usage: Sequence[PredicateUsage],
    sources: set[str],
) -> list[PredicateUsage]:
    """근거 이름 집합에 걸리는 usage를 고른다."""
    return [
        item
        for item in usage
        if item.name in sources or normalize_vocabulary_name(item.name) in sources
    ]


def _prepare(
    proposed_name: str,
    source_candidates: Sequence[str],
    *,
    known: Sequence[str],
    seen: set[str],
    observed: set[str],
) -> tuple[str, set[str]] | GuardRejection:
    """이름 정규화부터 관측 증거까지 공통 가드를 순서대로 검사한다.

    통과하면 정규화 이름과 근거 이름 집합을 돌려주고, 아니면 첫 위반
    사유로 기각을 돌려준다. 스키마 검증(규칙 4)은 모델이 서로 달라
    호출자가 맡는다.
    """
    normalized = normalize_vocabulary_name(proposed_name)
    if not normalized:
        return GuardRejection(name=proposed_name, reason="이름이 비었다")
    if normalized in set(known):
        return GuardRejection(name=normalized, reason="기존 엔트리 개정 금지")
    if normalized in seen:
        return GuardRejection(name=normalized, reason="제안 내 중복")
    sources = {normalize_vocabulary_name(candidate) for candidate in source_candidates}
    sources.update(source_candidates)
    sources.add(normalized)
    sources.discard("")
    if not sources & observed:
        return GuardRejection(name=normalized, reason="관측 증거 없음")
    return normalized, sources


def _guard_predicates(
    proposed: Sequence[ProposedPredicateEntry],
    *,
    current: ExtractionVocabulary,
    predicate_usage: Sequence[PredicateUsage],
    observed: set[str],
) -> tuple[list[PredicateEntry], list[GuardRejection], list[str]]:
    """predicate 제안을 항목별로 판정한다."""
    entries: list[PredicateEntry] = []
    rejections: list[GuardRejection] = []
    covered: list[str] = []
    seen: set[str] = set()

    for item in proposed:
        prepared = _prepare(
            item.name,
            item.source_candidates,
            known=current.predicates,
            seen=seen,
            observed=observed,
        )
        if isinstance(prepared, GuardRejection):
            rejections.append(prepared)
            continue
        normalized, sources = prepared

        try:
            entry = PredicateEntry.model_validate(
                {
                    "name": normalized,
                    "definition": item.definition,
                    "domain": item.domain,
                    "value_type": item.value_type,
                    "enum_values": item.enum_values,
                    "examples": item.examples,
                }
            )
        except ValidationError as error:
            rejections.append(
                GuardRejection(
                    name=normalized,
                    reason=(f"스키마 검증 실패: {_summarize_validation_error(error)}"),
                )
            )
            continue

        if entry.value_type == "enum":
            matched = _matched_usage(predicate_usage, sources)
            observed_values: set[str] = set()
            for usage in matched:
                observed_values.update(usage.observed_values)
            uncovered = sorted(observed_values - set(entry.enum_values))
            if uncovered:
                rejections.append(
                    GuardRejection(
                        name=normalized,
                        reason=(
                            f"enum 치역이 관측을 못 덮는다: {', '.join(uncovered)}"
                        ),
                    )
                )
                continue

        seen.add(normalized)
        entries.append(entry)
        covered.append(normalized)
        covered.extend(item.source_candidates)

    return entries, rejections, covered


def _guard_relations(
    proposed: Sequence[ProposedRelationEntry],
    *,
    current: ExtractionVocabulary,
    observed: set[str],
) -> tuple[list[RelationTypeEntry], list[GuardRejection], list[str]]:
    """relation 제안을 항목별로 판정한다.

    enum 치역 가드는 relation에 해당 개념이 없어 빠진다.
    """
    entries: list[RelationTypeEntry] = []
    rejections: list[GuardRejection] = []
    covered: list[str] = []
    seen: set[str] = set()

    for item in proposed:
        prepared = _prepare(
            item.name,
            item.source_candidates,
            known=current.relation_types,
            seen=seen,
            observed=observed,
        )
        if isinstance(prepared, GuardRejection):
            rejections.append(prepared)
            continue
        normalized, _ = prepared

        try:
            entry = RelationTypeEntry.model_validate(
                {
                    "name": normalized,
                    "definition": item.definition,
                    "domain": item.domain,
                    "range_": item.range_,
                    "examples": item.examples,
                }
            )
        except ValidationError as error:
            rejections.append(
                GuardRejection(
                    name=normalized,
                    reason=(f"스키마 검증 실패: {_summarize_validation_error(error)}"),
                )
            )
            continue

        seen.add(normalized)
        entries.append(entry)
        covered.append(normalized)
        covered.extend(item.source_candidates)

    return entries, rejections, covered


def _guard_absorptions(
    proposed: Sequence[SynonymAbsorption],
    *,
    current: ExtractionVocabulary,
    observed: set[str],
) -> tuple[list[SynonymAbsorption], list[GuardRejection], list[str]]:
    """동의어 흡수 판정을 검사한다.

    사전은 바뀌지 않는다. 통과분은 감사·리포트용으로만 남는다.
    """
    canonical = set(current.predicates) | set(current.relation_types)
    absorptions: list[SynonymAbsorption] = []
    rejections: list[GuardRejection] = []
    covered: list[str] = []

    for item in proposed:
        if item.canonical_name not in canonical:
            rejections.append(
                GuardRejection(
                    name=item.candidate_name,
                    reason="정본이 사전에 없다",
                )
            )
            continue
        candidates = {
            item.candidate_name,
            normalize_vocabulary_name(item.candidate_name),
        }
        candidates.discard("")
        if not candidates & observed:
            rejections.append(
                GuardRejection(
                    name=item.candidate_name,
                    reason="흡수 대상이 관측되지 않았다",
                )
            )
            continue
        absorptions.append(item)
        covered.append(item.candidate_name)

    return absorptions, rejections, covered


def guard_convergence(
    proposal: VocabularyConvergenceProposal,
    *,
    current: ExtractionVocabulary,
    predicate_usage: Sequence[PredicateUsage],
    relation_usage: Sequence[RelationUsage],
) -> ConvergenceGuardResult:
    """LLM 제안을 기계 가드로 걸러 통과분과 기각분을 나눈다."""
    predicate_observed = _observed_names(predicate_usage, current.predicates)
    relation_observed = _observed_names(relation_usage, current.relation_types)

    predicate_entries, predicate_rejections, predicate_covered = _guard_predicates(
        proposal.predicate_entries,
        current=current,
        predicate_usage=predicate_usage,
        observed=predicate_observed,
    )
    relation_entries, relation_rejections, relation_covered = _guard_relations(
        proposal.relation_entries,
        current=current,
        observed=relation_observed,
    )
    absorptions, absorption_rejections, absorption_covered = _guard_absorptions(
        proposal.absorptions,
        current=current,
        observed=predicate_observed | relation_observed,
    )

    covered: list[str] = []
    for name in (
        *predicate_covered,
        *relation_covered,
        *absorption_covered,
    ):
        if name and name not in covered:
            covered.append(name)

    return ConvergenceGuardResult(
        predicate_entries=tuple(predicate_entries),
        relation_entries=tuple(relation_entries),
        absorptions=tuple(absorptions),
        rejections=(
            *predicate_rejections,
            *relation_rejections,
            *absorption_rejections,
        ),
        covered_names=tuple(covered),
    )


def merge_vocabulary(
    current: ExtractionVocabulary,
    guarded: ConvergenceGuardResult,
    *,
    version: str,
) -> ExtractionVocabulary:
    """현행 어휘에 통과분을 더한 새 스냅샷을 만든다.

    이름 목록을 항상 명시해서 넘긴다. `ExtractionVocabulary`는 이름
    목록이 비었을 때만 entry에서 파생시키므로, entry 없이 이름만 있는
    예전 스냅샷을 병합하면 그 이름들이 조용히 사라진다.
    """
    predicates = (
        *current.predicates,
        *(entry.name for entry in guarded.predicate_entries),
    )
    relation_types = (
        *current.relation_types,
        *(entry.name for entry in guarded.relation_entries),
    )
    return ExtractionVocabulary(
        snapshot_id=version,
        predicates=predicates,
        relation_types=relation_types,
        entity_type_entries=current.entity_type_entries,
        predicate_entries=(
            *current.predicate_entries,
            *guarded.predicate_entries,
        ),
        relation_type_entries=(
            *current.relation_type_entries,
            *guarded.relation_entries,
        ),
    )
