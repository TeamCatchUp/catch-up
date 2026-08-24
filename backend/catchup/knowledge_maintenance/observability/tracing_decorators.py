from __future__ import annotations

import functools
from collections.abc import Awaitable
from collections.abc import Callable
from contextlib import AbstractContextManager
from contextlib import nullcontext
from typing import Any
from typing import TypeVar

from catchup.knowledge_maintenance.contracts.extraction import KnowledgeCandidateBatch
from catchup.knowledge_maintenance.contracts.extraction import (
    KnowledgeExtractionRequest,
)
from catchup.knowledge_maintenance.domain.observation import MetadataEntity
from catchup.knowledge_maintenance.domain.observation import NormalizedObservation
from catchup.knowledge_maintenance.domain.source_version import SourceVersion
from catchup.knowledge_maintenance.observability.tracing import llm_invoke_config
from catchup.knowledge_maintenance.observability.tracing import user_chat_trace_id
from catchup.observability.langfuse.configs import get_langfuse_client
from catchup.observability.logging import get_logger

logger = get_logger(__name__)

_Normalize = TypeVar("_Normalize", bound=Callable[..., NormalizedObservation])


def _safe_span(
    client: Any,
    trace_id: str,
    *,
    name: str,
    input: Any = None,
) -> AbstractContextManager[Any]:
    """
    span을 열되, 실패하더라도 호출자의 동작을 중단하지 않고 로그만 남긴다.
    """
    try:
        return client.start_as_current_observation(
            trace_context={"trace_id": trace_id},
            name=name,
            as_type="span",
            input=input,
        )
    except Exception as error:
        logger.warning(
            "langfuse_span_open_failed",
            name=name,
            trace_id=trace_id,
            error=str(error),
        )
        return nullcontext(None)


def _safe_update(span: Any, **output: Any) -> None:
    if span is None:
        return
    try:
        span.update(output=output)
    except Exception as error:
        logger.warning("langfuse_span_update_failed", error=str(error))


def _metadata_entity_dict(entity: MetadataEntity) -> dict[str, Any]:
    """
    `MetadataEntity`를 JSON 직렬화 가능한 dict으로 변환한다.
    """
    return {
        "entity_type": entity.entity_type,
        "external_key": entity.external_key,
        "display_name": entity.display_name,
        "attributes": dict(entity.attributes),
    }


def trace_normalize(normalize: _Normalize) -> _Normalize:

    @functools.wraps(normalize)
    def wrapper(self: Any, source_version: SourceVersion) -> NormalizedObservation:
        client = get_langfuse_client()
        if client is None:
            return normalize(self, source_version)

        trace_id = user_chat_trace_id(
            workspace_id=source_version.workspace_id,
            external_document_id=source_version.source_identity.external_document_id,
        )
        with _safe_span(
            client,
            trace_id,
            name="normalize",
            input={"content": source_version.content},
        ) as span:
            result = normalize(self, source_version)
            _safe_update(
                span,
                content=result.content,
                metadata_entities=[
                    _metadata_entity_dict(entity)
                    for entity in result.metadata_entities
                ],
                observation_kind=str(result.observation_kind),
            )
            return result

    return wrapper


def trace_extract(
    extract: Callable[..., Awaitable[KnowledgeCandidateBatch]],
) -> Callable[[Any, KnowledgeExtractionRequest], Awaitable[KnowledgeCandidateBatch]]:

    @functools.wraps(extract)
    async def wrapper(
        self: Any,
        request: KnowledgeExtractionRequest,
    ) -> KnowledgeCandidateBatch:
        client = get_langfuse_client()
        if (
            client is None
            or request.workspace_id is None
            or request.external_document_id is None
        ):
            return await extract(self, request, invoke_config=None)

        trace_id = user_chat_trace_id(
            workspace_id=request.workspace_id,
            external_document_id=request.external_document_id,
        )
        with _safe_span(
            client,
            trace_id,
            name="extract",
            input={
                "content": request.content,
                "source_type": request.source_type,
                "contract_version": request.contract_version,
            },
        ) as span:
            invoke_config = llm_invoke_config(trace_id)
            batch = await extract(self, request, invoke_config=invoke_config)
            _safe_update(
                span,
                entities=[entity.model_dump(mode="json") for entity in batch.entities],
                claims=[claim.model_dump(mode="json") for claim in batch.claims],
                relations=[
                    relation.model_dump(mode="json")
                    for relation in batch.relation_assertions
                ],
            )
            return batch

    return wrapper
