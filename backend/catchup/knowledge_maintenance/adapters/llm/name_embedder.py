"""기존 임베딩 인프라를 이름 벡터 포트에 맞춰 감싼다."""

from __future__ import annotations

import time
from collections.abc import Sequence
from typing import Protocol

from catchup.knowledge_maintenance.ports.name_embedder import NameEmbeddingError
from catchup.observability.logging import get_logger

logger = get_logger(__name__)


class _Embeddings(Protocol):
    """임베딩 모델에서 쓰는 호출 하나만 추린다."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...


class _EmbeddingService(Protocol):
    """임베딩 서비스에서 쓰는 호출 하나만 추린다.

    구체 타입을 그대로 받지 않는 이유는 이 어댑터가 제공자별 설정과
    무관하고, 좁은 계약만 요구해야 시험에서 가짜를 끼우기 쉽기 때문이다.
    """

    def get_embedder(self) -> _Embeddings: ...


class EmbeddingServiceNameEmbedder:
    """임베딩 서비스로 이름 목록을 벡터 목록으로 바꾼다.

    감싸는 대상은 `components/embedder`의 임베딩 서비스다. 이 어댑터가
    있어서 해소 서비스는 어떤 제공자를 쓰는지, 벡터 저장소가 있는지
    모르고도 유사도 blocking을 돌릴 수 있다.

    로그에는 개수와 걸린 초만 남긴다. 이름 자체는 남기지 않는다. 후보
    이름은 원문에서 흘러든 텍스트이고 감사 로그는 오래 남기 때문이다.
    """

    def __init__(self, service: _EmbeddingService) -> None:
        self._embeddings = service.get_embedder()

    def embed(self, names: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        """이름마다 벡터 하나를 돌려준다.

        Raises:
            NameEmbeddingError: 이름이 비었거나, 호출이 실패했거나, 받은
                벡터 수가 이름 수와 다를 때 던진다.
        """
        texts = list(names)
        if not texts:
            return ()
        if any(not text.strip() for text in texts):
            raise NameEmbeddingError("빈 이름은 벡터로 바꿀 수 없다.")

        started = time.perf_counter()
        try:
            vectors = self._embeddings.embed_documents(texts)
        except Exception as error:
            logger.warning(
                "name_embedding_failed",
                reason="backend_error",
                error_type=type(error).__name__,
                name_count=len(texts),
                elapsed=round(time.perf_counter() - started, 3),
            )
            raise NameEmbeddingError("이름 임베딩 호출이 실패했다.") from error
        elapsed = round(time.perf_counter() - started, 3)

        if len(vectors) != len(texts):
            logger.warning(
                "name_embedding_failed",
                reason="count_mismatch",
                name_count=len(texts),
                vector_count=len(vectors),
                elapsed=elapsed,
            )
            raise NameEmbeddingError("받은 벡터 수가 이름 수와 다르다.")

        logger.info(
            "name_embedding_completed",
            name_count=len(texts),
            elapsed=elapsed,
        )
        return tuple(tuple(float(value) for value in vector) for vector in vectors)
