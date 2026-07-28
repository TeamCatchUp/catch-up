from __future__ import annotations

from dataclasses import dataclass

from langchain_core.language_models import BaseChatModel

from catchup.knowledge_maintenance.contracts.extraction import KnowledgeCandidateBatch
from catchup.knowledge_maintenance.contracts.extraction import (
    KnowledgeExtractionRequest,
)
from catchup.knowledge_maintenance.domain.observation import MetadataEntity
from catchup.prompts.loader import prompt_loader

TEMPLATE_PATH = "knowledge_maintenance/extract_knowledge_candidates.j2"
CONTRACT_ID = "catchup.knowledge_candidates"


@dataclass(frozen=True, slots=True)
class ExtractionDiagnostics:
    """추출 한 번의 관찰값을 담는다.

    Attributes:
        raw_output: 검증 전 LLM 출력을 그대로 보존한다.
        parse_error: 계약 위반으로 실패했을 때의 사유를 나타낸다.
    """

    raw_output: dict | None = None
    parse_error: str | None = None


class StructuredKnowledgeExtractor:
    """구조화 출력을 요구해 지식 후보를 뽑는다.

    자유 텍스트 문장 대신 `subject + predicate + value` 구조를 강제한다.
    자연어 관계 문장을 Claim으로 그대로 옮기지 않기 위함이다.
    """

    def __init__(self, llm: BaseChatModel) -> None:
        self._structured = llm.with_structured_output(
            KnowledgeCandidateBatch,
            method="function_calling",
            include_raw=True,
        )

    async def extract(
        self,
        request: KnowledgeExtractionRequest,
    ) -> KnowledgeCandidateBatch:
        """원문 하나에서 지식 후보를 뽑는다."""
        batch, _ = await self.extract_with_diagnostics(request)
        if batch is None:
            raise ValueError("추출 결과가 계약을 만족하지 않는다.")
        return batch

    async def extract_with_diagnostics(
        self,
        request: KnowledgeExtractionRequest,
    ) -> tuple[KnowledgeCandidateBatch | None, ExtractionDiagnostics]:
        """관찰 단계에서 실패한 출력까지 함께 돌려준다.

        계약이 아직 확정되지 않은 동안에는 무엇이 왜 거부됐는지가
        성공한 결과만큼 중요하다.
        """
        rendered = prompt_loader.get_prompt(
            TEMPLATE_PATH,
            content=request.content,
            source_type=request.source_type,
            metadata_entities=_with_local_keys(request.metadata_entities),
            vocabulary=request.vocabulary,
        )

        response = await self._structured.ainvoke(rendered)
        raw = response.get("raw")

        parsed = response.get("parsed")
        if parsed is not None:
            return parsed, ExtractionDiagnostics(raw_output=_dump(raw))

        error = response.get("parsing_error")
        return None, ExtractionDiagnostics(
            raw_output=_dump(raw),
            parse_error=str(error) if error is not None else "unknown",
        )


def _with_local_keys(
    metadata_entities: tuple[MetadataEntity, ...],
) -> list[dict[str, str]]:
    """이미 확정된 Entity에 추출 run 안에서 쓸 참조 키를 붙인다.

    `local_key`는 한 번의 추출 안에서만 유효하므로 저장되는 MetadataEntity에
    두지 않는다. LLM이 이 키로 subject를 가리키게 하려고 여기서만 만든다.
    """
    return [
        {
            "local_key": f"m{index}",
            "display_name": entity.display_name,
            "entity_type": entity.entity_type,
        }
        for index, entity in enumerate(metadata_entities, start=1)
    ]


def _dump(raw: object) -> dict | None:
    """LLM 원본 응답을 JSON 호환 형태로 바꾼다."""
    if raw is None:
        return None
    if hasattr(raw, "model_dump"):
        return raw.model_dump(mode="json")
    return {"repr": repr(raw)}
