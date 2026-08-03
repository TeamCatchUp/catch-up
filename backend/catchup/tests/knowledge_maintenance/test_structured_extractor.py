from __future__ import annotations

from datetime import datetime
from datetime import timezone
from typing import Any

import pytest

from catchup.knowledge_maintenance.adapters.llm.structured_extractor import (
    StructuredKnowledgeExtractor,
)
from catchup.knowledge_maintenance.contracts.extraction import EntityCandidateDraft
from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary
from catchup.knowledge_maintenance.contracts.extraction import KnowledgeCandidateBatch
from catchup.knowledge_maintenance.contracts.extraction import (
    KnowledgeExtractionRequest,
)
from catchup.knowledge_maintenance.domain.observation import MetadataEntity


class _StubStructuredRunnable:
    def __init__(self, response: dict[str, Any]) -> None:
        self._response = response
        self.rendered_prompt: str | None = None

    async def ainvoke(self, prompt: str) -> dict[str, Any]:
        self.rendered_prompt = prompt
        return self._response


class _StubChatModel:
    """with_structured_output만 흉내내는 최소 대역이다."""

    def __init__(self, response: dict[str, Any]) -> None:
        self.runnable = _StubStructuredRunnable(response)

    def with_structured_output(self, *args: Any, **kwargs: Any):
        return self.runnable


def _request(**overrides: object) -> KnowledgeExtractionRequest:
    values: dict[str, object] = {
        "content": "결제 기능은 9월 출시 예정이다.",
        "source_type": "jira",
        "contract_version": "1",
    }
    values.update(overrides)
    return KnowledgeExtractionRequest.model_validate(values)


@pytest.mark.asyncio
async def test_known_entities_are_passed_to_the_prompt() -> None:
    llm = _StubChatModel({"parsed": KnowledgeCandidateBatch(), "raw": None})
    extractor = StructuredKnowledgeExtractor(llm)

    await extractor.extract(
        _request(
            metadata_entities=(
                MetadataEntity(
                    entity_type="customer",
                    external_key="u1",
                    display_name="예시고객사",
                ),
            ),
        )
    )

    prompt = llm.runnable.rendered_prompt
    assert "예시고객사" in prompt
    assert "customer" in prompt


@pytest.mark.asyncio
async def test_vocabulary_is_passed_to_the_prompt() -> None:
    llm = _StubChatModel({"parsed": KnowledgeCandidateBatch(), "raw": None})
    extractor = StructuredKnowledgeExtractor(llm)

    await extractor.extract(
        _request(
            vocabulary=ExtractionVocabulary(
                predicates=("release_month",),
                relation_types=("depends_on",),
            )
        )
    )

    prompt = llm.runnable.rendered_prompt
    assert "release_month" in prompt
    assert "depends_on" in prompt


@pytest.mark.asyncio
async def test_predicate_and_relation_vocabularies_are_not_mixed() -> None:
    llm = _StubChatModel({"parsed": KnowledgeCandidateBatch(), "raw": None})
    extractor = StructuredKnowledgeExtractor(llm)

    await extractor.extract(
        _request(
            vocabulary=ExtractionVocabulary(
                predicates=("release_month",),
                relation_types=("depends_on",),
            )
        )
    )

    prompt = llm.runnable.rendered_prompt
    predicate_section = prompt.index("release_month")
    relation_section = prompt.index("depends_on")
    # 두 어휘가 각자의 절에 놓여야 LLM이 용도를 구분한다.
    assert predicate_section != relation_section


@pytest.mark.asyncio
async def test_contract_violation_is_reported_instead_of_raising() -> None:
    llm = _StubChatModel(
        {
            "parsed": None,
            "raw": None,
            "parsing_error": "subject를 찾을 수 없다",
        }
    )
    extractor = StructuredKnowledgeExtractor(llm)

    batch, diagnostics = await extractor.extract_with_diagnostics(_request())

    assert batch is None
    assert "subject" in diagnostics.parse_error


@pytest.mark.asyncio
async def test_parsed_batch_is_returned_as_is() -> None:
    expected = KnowledgeCandidateBatch(
        entities=[
            EntityCandidateDraft(
                local_key="e1",
                proposed_type="feature",
                proposed_name="결제 기능",
            )
        ]
    )
    llm = _StubChatModel({"parsed": expected, "raw": None})
    extractor = StructuredKnowledgeExtractor(llm)

    batch = await extractor.extract(_request())

    assert batch.entities[0].proposed_name == "결제 기능"


@pytest.mark.asyncio
async def test_reference_time_is_rendered_into_the_prompt() -> None:
    llm = _StubChatModel({"parsed": KnowledgeCandidateBatch(), "raw": None})
    extractor = StructuredKnowledgeExtractor(llm)

    await extractor.extract(
        _request(reference_time=datetime(2026, 8, 1, tzinfo=timezone.utc))
    )

    prompt = llm.runnable.rendered_prompt
    assert "2026-08-01" in prompt


@pytest.mark.asyncio
async def test_missing_reference_time_keeps_conservative_instruction() -> None:
    llm = _StubChatModel({"parsed": KnowledgeCandidateBatch(), "raw": None})
    extractor = StructuredKnowledgeExtractor(llm)

    await extractor.extract(_request(reference_time=None))

    prompt = llm.runnable.rendered_prompt
    # 기준 시각이 없으면 상대 시간을 추측하지 말라는 보수 지시만 남는다.
    assert "reference time" not in prompt
    assert "Do not guess dates for" in prompt


@pytest.mark.asyncio
async def test_validity_bounds_demand_a_full_calendar_date() -> None:
    """경계는 값과 달리 부분 날짜를 허용하지 않는다고 지시해야 한다."""
    llm = _StubChatModel({"parsed": KnowledgeCandidateBatch(), "raw": None})
    extractor = StructuredKnowledgeExtractor(llm)

    await extractor.extract(
        _request(reference_time=datetime(2026, 8, 1, tzinfo=timezone.utc))
    )

    prompt = llm.runnable.rendered_prompt
    assert "full calendar date (`YYYY-MM-DD`)" in prompt
    assert "leave the bound empty" in prompt


@pytest.mark.asyncio
async def test_validity_bound_format_holds_without_reference_time() -> None:
    """기준 시각이 없어도 경계 형식 요구는 유지된다."""
    llm = _StubChatModel({"parsed": KnowledgeCandidateBatch(), "raw": None})
    extractor = StructuredKnowledgeExtractor(llm)

    await extractor.extract(_request(reference_time=None))

    prompt = llm.runnable.rendered_prompt
    assert "full calendar date (`YYYY-MM-DD`)" in prompt
