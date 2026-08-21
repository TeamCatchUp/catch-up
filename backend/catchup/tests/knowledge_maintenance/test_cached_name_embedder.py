from __future__ import annotations

from collections.abc import Mapping
from collections.abc import Sequence

import pytest

from catchup.knowledge_maintenance.adapters.llm.name_embedder import CachedNameEmbedder
from catchup.knowledge_maintenance.ports.name_embedder import NameEmbeddingError

MODEL_ID = "test-embedding-model"
WORKSPACE_ID = 1


class _FakeCache:
    """포트와 같은 키 규칙으로 벡터를 기억하는 가짜 캐시다."""

    def __init__(self) -> None:
        self.rows: dict[tuple[int, str, str], tuple[float, ...]] = {}
        self.lookup_calls: list[tuple[int, str, tuple[str, ...]]] = []
        self.store_calls: list[tuple[int, str, tuple[str, ...]]] = []

    def lookup(
        self,
        *,
        workspace_id: int,
        model_id: str,
        normalized_names: Sequence[str],
    ) -> dict[str, tuple[float, ...]]:
        self.lookup_calls.append(
            (workspace_id, model_id, tuple(normalized_names))
        )
        found: dict[str, tuple[float, ...]] = {}
        for name in normalized_names:
            vector = self.rows.get((workspace_id, model_id, name))
            if vector is not None:
                found[name] = vector
        return found

    def store(
        self,
        *,
        workspace_id: int,
        model_id: str,
        vectors: Mapping[str, Sequence[float]],
    ) -> None:
        self.store_calls.append(
            (workspace_id, model_id, tuple(vectors.keys()))
        )
        for name, vector in vectors.items():
            key = (workspace_id, model_id, name)
            self.rows.setdefault(key, tuple(float(value) for value in vector))


class _FailingCache(_FakeCache):
    """조회와 저장이 모두 터지는 캐시다."""

    def lookup(self, **kwargs: object) -> dict[str, tuple[float, ...]]:
        raise RuntimeError("캐시 조회가 실패했다")

    def store(self, **kwargs: object) -> None:
        raise RuntimeError("캐시 저장이 실패했다")


class _CountingEmbedder:
    """부른 이름을 그대로 기록하고 이름마다 정해진 벡터를 주는 임베더다."""

    def __init__(self, vectors: dict[str, tuple[float, ...]]) -> None:
        self._vectors = vectors
        self.calls: list[tuple[str, ...]] = []

    def embed(self, names: Sequence[str]) -> tuple[tuple[float, ...], ...]:
        self.calls.append(tuple(names))
        return tuple(self._vectors[name] for name in names)


def _embedder(
    inner: _CountingEmbedder,
    cache: _FakeCache,
    *,
    model_id: str = MODEL_ID,
) -> CachedNameEmbedder:
    return CachedNameEmbedder(
        inner,
        cache,
        workspace_id=WORKSPACE_ID,
        model_id=model_id,
    )


def test_first_call_misses_everything_and_stores_it() -> None:
    """처음에는 모두 없어서 전부 임베딩하고 담아 둔다."""
    inner = _CountingEmbedder(
        {"slack": (1.0, 0.0), "지라": (0.0, 1.0)},
    )
    cache = _FakeCache()

    vectors = _embedder(inner, cache).embed(("Slack", "지라"))

    assert vectors == ((1.0, 0.0), (0.0, 1.0))
    assert inner.calls == [("slack", "지라")]
    assert cache.store_calls == [(WORKSPACE_ID, MODEL_ID, ("slack", "지라"))]


def test_second_call_hits_everything_without_embedding() -> None:
    """같은 이름을 다시 부르면 임베딩 호출이 한 번도 없다."""
    inner = _CountingEmbedder(
        {"slack": (1.0, 0.0), "지라": (0.0, 1.0)},
    )
    cache = _FakeCache()
    first = _embedder(inner, cache)
    first.embed(("Slack", "지라"))
    inner.calls.clear()

    vectors = _embedder(inner, cache).embed(("Slack", "지라"))

    assert vectors == ((1.0, 0.0), (0.0, 1.0))
    assert inner.calls == []


def test_partial_hit_embeds_only_the_missing_names() -> None:
    """일부만 담겨 있으면 없는 이름만 임베딩한다."""
    inner = _CountingEmbedder(
        {"slack": (1.0, 0.0), "지라": (0.0, 1.0)},
    )
    cache = _FakeCache()
    _embedder(inner, cache).embed(("Slack",))
    inner.calls.clear()

    vectors = _embedder(inner, cache).embed(("Slack", "지라"))

    assert vectors == ((1.0, 0.0), (0.0, 1.0))
    assert inner.calls == [("지라",)]


def test_other_model_does_not_reuse_the_vector() -> None:
    """모델이 다르면 벡터 공간이 달라 담아 둔 값을 쓰지 않는다."""
    inner = _CountingEmbedder({"slack": (1.0, 0.0)})
    cache = _FakeCache()
    _embedder(inner, cache).embed(("Slack",))
    inner.calls.clear()

    _embedder(inner, cache, model_id="other-model").embed(("Slack",))

    assert inner.calls == [("slack",)]


def test_same_name_twice_is_embedded_once() -> None:
    """표기만 다른 같은 이름은 한 번만 임베딩하고 같은 벡터를 준다."""
    inner = _CountingEmbedder({"slack": (1.0, 0.0)})
    cache = _FakeCache()

    vectors = _embedder(inner, cache).embed(("Slack", "  slack  "))

    assert vectors == ((1.0, 0.0), (1.0, 0.0))
    assert inner.calls == [("slack",)]


def test_empty_input_touches_neither_cache_nor_embedder() -> None:
    """이름이 없으면 조회도 임베딩도 하지 않는다."""
    inner = _CountingEmbedder({})
    cache = _FakeCache()

    assert _embedder(inner, cache).embed(()) == ()
    assert cache.lookup_calls == []
    assert inner.calls == []


def test_blank_name_is_rejected() -> None:
    """빈 이름은 벡터로 바꿀 수 없어 예외다."""
    inner = _CountingEmbedder({})

    with pytest.raises(NameEmbeddingError):
        _embedder(inner, _FakeCache()).embed(("  ",))


def test_cache_failure_falls_back_to_embedding() -> None:
    """캐시가 터져도 임베딩 결과로 이번 라운드를 마친다."""
    inner = _CountingEmbedder({"slack": (1.0, 0.0)})

    vectors = _embedder(inner, _FailingCache()).embed(("Slack",))

    assert vectors == ((1.0, 0.0),)
    assert inner.calls == [("slack",)]
