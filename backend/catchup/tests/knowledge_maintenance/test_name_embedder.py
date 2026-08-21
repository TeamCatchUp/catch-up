from __future__ import annotations

import pytest

from catchup.knowledge_maintenance.adapters.llm.name_embedder import (
    EmbeddingServiceNameEmbedder,
)
from catchup.knowledge_maintenance.ports.name_embedder import NameEmbeddingError


class _FakeEmbeddings:
    def __init__(self, vectors: list[list[float]] | None = None) -> None:
        self.vectors = vectors
        self.calls: list[list[str]] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        if self.vectors is None:
            raise RuntimeError("임베딩 백엔드가 응답하지 않았다")
        return self.vectors


class _FakeService:
    def __init__(self, embeddings: _FakeEmbeddings) -> None:
        self._embeddings = embeddings

    def get_embedder(self) -> _FakeEmbeddings:
        return self._embeddings


def _embedder(embeddings: _FakeEmbeddings) -> EmbeddingServiceNameEmbedder:
    return EmbeddingServiceNameEmbedder(_FakeService(embeddings))


def test_names_become_vectors() -> None:
    """이름 목록이 같은 순서의 벡터 목록으로 돌아온다."""
    embeddings = _FakeEmbeddings([[1.0, 0.0], [0.0, 1.0]])

    vectors = _embedder(embeddings).embed(("Slack", "슬랙"))

    assert vectors == ((1.0, 0.0), (0.0, 1.0))
    assert embeddings.calls == [["Slack", "슬랙"]]


def test_empty_input_skips_the_call() -> None:
    """이름이 없으면 호출하지 않고 빈 결과를 준다."""
    embeddings = _FakeEmbeddings([])

    assert _embedder(embeddings).embed(()) == ()
    assert embeddings.calls == []


def test_blank_name_is_rejected() -> None:
    """빈 이름은 벡터를 만들 수 없어 예외다."""
    embeddings = _FakeEmbeddings([[1.0, 0.0]])

    with pytest.raises(NameEmbeddingError):
        _embedder(embeddings).embed(("  ",))


def test_backend_failure_becomes_port_error() -> None:
    """백엔드 실패는 포트 예외로 바꾼다."""
    with pytest.raises(NameEmbeddingError):
        _embedder(_FakeEmbeddings(None)).embed(("Slack",))


def test_count_mismatch_becomes_port_error() -> None:
    """벡터 수가 이름 수와 다르면 짝을 지을 수 없어 예외다."""
    embeddings = _FakeEmbeddings([[1.0, 0.0]])

    with pytest.raises(NameEmbeddingError):
        _embedder(embeddings).embed(("Slack", "슬랙"))
