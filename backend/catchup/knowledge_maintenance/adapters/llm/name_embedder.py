"""기존 임베딩 인프라를 이름 벡터 포트에 맞춰 감싼다."""

from __future__ import annotations

import time
from collections.abc import Sequence
from typing import Protocol

from catchup.knowledge_maintenance.domain.entity_resolution import normalize_name
from catchup.knowledge_maintenance.ports.name_embedder import NameEmbedder
from catchup.knowledge_maintenance.ports.name_embedder import NameEmbeddingCache
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


def _read_model_id(service: object, embeddings: object) -> str:
    """임베딩 서비스가 실제로 쓰는 모델 식별자를 찾는다.

    제공자마다 식별자를 들고 있는 자리가 다르다. Bedrock 서비스는
    `model_id`에, langchain 임베더는 `model` 또는 `model_id`에 둔다.
    서비스부터 보고 없으면 임베더를 본다.

    Returns:
        찾은 식별자를 준다. 어디에도 없으면 빈 문자열을 준다. 캐시를
        끼울지 말지는 부르는 쪽이 정한다.
    """
    for holder in (service, embeddings):
        for attribute in ("model_id", "model"):
            value = getattr(holder, attribute, None)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


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
        self._model_id = _read_model_id(service, self._embeddings)

    @property
    def model_id(self) -> str:
        """벡터를 만든 임베딩 모델 식별자를 돌려준다.

        캐시가 키에 넣을 값이다. 모델이 다르면 벡터 공간이 달라 옛 벡터를
        새 모델 벡터와 나란히 견줄 수 없어, 부르는 쪽이 하드코딩하지 않고
        실제로 쓰는 모델에서 가져가야 한다.
        """
        return self._model_id

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


def cached_name_embedder(
    embedder: EmbeddingServiceNameEmbedder,
    cache: NameEmbeddingCache,
    *,
    workspace_id: int,
) -> NameEmbedder:
    """임베더에 캐시를 두르되 모델 식별자가 없으면 그대로 돌려준다.

    캐시 키에는 모델 식별자가 들어가야 한다. 모델이 다르면 벡터 공간이
    달라 옛 벡터를 새 모델 벡터와 나란히 견줄 수 없기 때문이다. 식별자를
    못 읽었는데 아무 값이나 채워 담으면 모델을 바꾼 뒤 옛 벡터를 새
    벡터로 잘못 쓰게 되므로, 그럴 때는 캐시를 끼우지 않는다. 캐시가
    없으면 임베딩을 다시 부를 뿐이고 해소 결과는 같다.
    """
    model_id = embedder.model_id
    if not model_id:
        logger.warning("name_embedding_cache_disabled", reason="unknown_model")
        return embedder
    return CachedNameEmbedder(
        embedder,
        cache,
        workspace_id=workspace_id,
        model_id=model_id,
    )


class CachedNameEmbedder:
    """이미 바꿔 본 이름은 담아 둔 벡터로 돌려주고 나머지만 임베딩한다.

    해소는 라운드마다 이번 후보 이름과 살아 있는 노드 별칭 전부를 벡터로
    바꾼다. 별칭이 쌓이면 이미 바꿔 본 이름을 매 라운드 다시 임베딩하게
    되어, 라운드마다 같은 호출을 수백 번 되풀이한다. 이 자리가 그 되풀이를
    걷어낸다.

    포트 계약을 그대로 지키는 감싸는 계층이라 해소 서비스는 캐시가 끼어
    있는지 모른다. 캐시를 빼도 결과가 같아야 하므로 판정 순서나 벡터 값에 손을
    대지 않는다.

    담고 찾는 키는 정규화 이름이고, 임베딩에 보내는 글자도 정규화 이름
    그대로다. 담을 때와 찾을 때 글자가 다르면 같은 키에 표기마다 다른
    벡터가 붙어 어느 것이 담긴 값인지 알 수 없어진다. 정규화는 NFKC와
    공백 접기와 casefold까지라 이름의 뜻이 바뀌지 않는다.

    캐시가 터져도 예외를 올리지 않는다. 캐시는 다시 만들 수 있는 사본이라
    없으면 임베딩을 그냥 부르면 되고, 조회 실패로 해소를 멈출 이유가 없다.
    """

    def __init__(
        self,
        embedder: NameEmbedder,
        cache: NameEmbeddingCache,
        *,
        workspace_id: int,
        model_id: str,
    ) -> None:
        """캐시를 두른 임베더를 만든다.

        Args:
            embedder: 담긴 값이 없을 때 실제로 부를 임베더를 받는다.
            cache: 벡터를 담고 찾는 자리를 받는다.
            workspace_id: 이 임베더가 도는 workspace를 받는다.
            model_id: embedder가 쓰는 모델 식별자를 받는다. 모델이 다르면
                벡터 공간이 달라 옛 벡터를 그대로 쓸 수 없다.
        """
        self._embedder = embedder
        self._cache = cache
        self._workspace_id = workspace_id
        self._model_id = model_id

    def embed(self, names: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        """이름마다 벡터 하나를 돌려준다.

        Raises:
            NameEmbeddingError: 이름이 비었거나, 담긴 값이 없는 이름의
                임베딩이 실패했을 때 던진다.
        """
        texts = list(names)
        if not texts:
            return ()
        if any(not text.strip() for text in texts):
            raise NameEmbeddingError("빈 이름은 벡터로 바꿀 수 없다.")

        keys = [normalize_name(text) for text in texts]
        wanted = list(dict.fromkeys(keys))
        found = self._lookup(wanted)

        missing = [key for key in wanted if key not in found]
        logger.info(
            "name_embedding_cache_checked",
            workspace_id=self._workspace_id,
            hit_count=len(wanted) - len(missing),
            miss_count=len(missing),
        )
        if missing:
            fresh = self._embedder.embed(missing)
            if len(fresh) != len(missing):
                raise NameEmbeddingError("받은 벡터 수가 이름 수와 다르다.")
            found.update(dict(zip(missing, fresh, strict=True)))
            self._store({key: found[key] for key in missing})

        return tuple(found[key] for key in keys)

    def _lookup(self, names: list[str]) -> dict[str, tuple[float, ...]]:
        """담긴 벡터를 찾되 실패는 "하나도 없음"으로 읽는다."""
        try:
            return dict(
                self._cache.lookup(
                    workspace_id=self._workspace_id,
                    model_id=self._model_id,
                    normalized_names=names,
                )
            )
        except Exception as error:
            logger.warning(
                "name_embedding_cache_lookup_failed",
                workspace_id=self._workspace_id,
                name_count=len(names),
                error_type=type(error).__name__,
            )
            return {}

    def _store(self, vectors: dict[str, tuple[float, ...]]) -> None:
        """새로 얻은 벡터를 담되 실패해도 이번 라운드를 막지 않는다."""
        try:
            self._cache.store(
                workspace_id=self._workspace_id,
                model_id=self._model_id,
                vectors=vectors,
            )
        except Exception as error:
            logger.warning(
                "name_embedding_cache_store_failed",
                workspace_id=self._workspace_id,
                name_count=len(vectors),
                error_type=type(error).__name__,
            )
