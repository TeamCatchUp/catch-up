from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Any

from langchain_core.language_models import BaseChatModel

from catchup.knowledge_maintenance.adapters.llm.prompt_versioning import (
    versioned_prompt,
)
from catchup.knowledge_maintenance.adapters.llm.retry import aretry_llm_call
from catchup.knowledge_maintenance.contracts.extraction import ExtractionVocabulary
from catchup.knowledge_maintenance.contracts.extraction import KnowledgeCandidateBatch
from catchup.knowledge_maintenance.contracts.extraction import (
    KnowledgeExtractionRequest,
)
from catchup.knowledge_maintenance.contracts.extraction import metadata_local_key
from catchup.knowledge_maintenance.domain.observation import MetadataEntity
from catchup.knowledge_maintenance.observability.tracing_decorators import trace_extract
from catchup.knowledge_maintenance.ports.extraction import ExtractionAPIError
from catchup.knowledge_maintenance.ports.extraction import ExtractionContractError
from catchup.observability.logging import get_logger
from catchup.prompts.loader import prompt_loader

TEMPLATE_PATH = "knowledge_maintenance/extract_knowledge_candidates.j2"
PROMPT_VERSION = versioned_prompt(TEMPLATE_PATH)
CONTRACT_ID = "catchup.knowledge_candidates"

logger = get_logger(__name__)


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

    @trace_extract
    async def extract(
        self,
        request: KnowledgeExtractionRequest,
        *,
        invoke_config: dict[str, Any] | None = None,
    ) -> KnowledgeCandidateBatch:
        """원문 하나에서 지식 후보를 뽑는다.

        `invoke_config`는 Langfuse Callback Handler를 담고 있음.
        `trace_extract` 데코레이터가 이를 채워 넣고, 원본 메서드는 이를 사용하지 않음.
        """
        batch, diagnostics = await self.extract_with_diagnostics(
            request, invoke_config=invoke_config
        )
        if batch is None:
            raise ExtractionContractError(
                diagnostics.parse_error
                or "추출 결과가 계약을 만족하지 않는다.",
                raw_output=diagnostics.raw_output,
            )
        return batch

    async def extract_with_diagnostics(
        self,
        request: KnowledgeExtractionRequest,
        *,
        invoke_config: dict[str, Any] | None = None,
    ) -> tuple[KnowledgeCandidateBatch | None, ExtractionDiagnostics]:
        """관찰 단계에서 실패한 출력까지 함께 돌려준다.

        계약이 아직 확정되지 않은 동안에는 무엇이 왜 거부됐는지가
        성공한 결과만큼 중요하다.
        """
        known_entities = _with_local_keys(request.metadata_entities)
        rendered = prompt_loader.get_prompt(
            TEMPLATE_PATH,
            content=request.content,
            source_type=request.source_type,
            metadata_entities=known_entities,
            vocabulary=request.vocabulary,
            # datetime을 그대로 넘기면 템플릿이 `2026-08-01 00:00:00+00:00`
            # 꼴로 찍는다. ISO 8601이 모델에게 덜 헷갈린다.
            reference_time=(
                request.reference_time.isoformat()
                if request.reference_time
                else None
            ),
        )

        # 무엇을 근거로 무엇을 물었는지 남긴다. 본문과 이름은 싣지 않는다.
        # 상담 원문은 개인정보를 담고 감사 로그는 오래 남기 때문이다.
        vocabulary = request.vocabulary or ExtractionVocabulary()
        call_context = {
            "source_type": request.source_type,
            "contract_version": request.contract_version,
            "content_length": len(request.content),
            "content_hash": _content_fingerprint(request.content),
            "metadata_entity_count": len(known_entities),
            "ontology_version": vocabulary.snapshot_id or None,
            "predicate_count": len(vocabulary.predicates),
            "relation_type_count": len(vocabulary.relation_types),
            "reference_time": (
                request.reference_time.isoformat()
                if request.reference_time
                else None
            ),
        }
        logger.info("knowledge_extraction_started", **call_context)

        started = time.perf_counter()
        try:
            response = await aretry_llm_call(
                lambda: self._structured.ainvoke(rendered, config=invoke_config),
                subject="knowledge_extraction",
            )
        except Exception as error:
            logger.exception(
                "knowledge_extraction_failed",
                error_type=type(error).__name__,
                elapsed=round(time.perf_counter() - started, 3),
                **call_context,
            )
            raise ExtractionAPIError(str(error)) from error
        elapsed = round(time.perf_counter() - started, 3)
        raw = response.get("raw")

        parsed = response.get("parsed")
        if parsed is not None:
            known_keys = frozenset(
                entity["local_key"] for entity in known_entities
            )
            try:
                parsed.validate_metadata_references(known_keys)
            except ValueError as error:
                logger.warning(
                    "knowledge_extraction_rejected",
                    reason="unknown_metadata_reference",
                    detail=str(error),
                    elapsed=elapsed,
                    **call_context,
                )
                return None, ExtractionDiagnostics(
                    raw_output=_dump(raw),
                    parse_error=str(error),
                )

            logger.info(
                "knowledge_extraction_completed",
                elapsed=elapsed,
                entity_count=len(parsed.entities),
                claim_count=len(parsed.claims),
                relation_count=len(parsed.relation_assertions),
                # 어휘를 벗어난 predicate는 막지 않고 표시만 한다. 새 개념일
                # 수도 있고 동의어일 수도 있어 형식 검사로는 가릴 수 없다.
                off_vocabulary_predicates=sorted(
                    {claim.predicate for claim in parsed.claims}
                    - set(vocabulary.predicates)
                )
                if vocabulary.predicates
                else [],
                **call_context,
            )
            return parsed, ExtractionDiagnostics(raw_output=_dump(raw))

        error = response.get("parsing_error")
        logger.warning(
            "knowledge_extraction_rejected",
            reason="contract_violation",
            detail=str(error) if error is not None else "unknown",
            elapsed=elapsed,
            **call_context,
        )
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
            "local_key": metadata_local_key(index),
            "display_name": entity.display_name,
            "entity_type": entity.entity_type,
        }
        for index, entity in enumerate(metadata_entities, start=1)
    ]


def _dump(raw: object) -> dict | None:
    """LLM 원본 응답을 JSON 호환 형태로 바꾼다."""
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    if hasattr(raw, "model_dump"):
        return raw.model_dump(mode="json")
    return {"repr": repr(raw)}


def _content_fingerprint(content: str) -> str:
    """본문 대신 남길 지문을 만든다.

    같은 원문을 여러 번 추출했는지 로그만으로 판별할 수 있게 하되, 본문
    자체는 남기지 않는다.
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
