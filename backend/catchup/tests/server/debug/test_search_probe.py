from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.documents import Document

from catchup.server.debug.api import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)


def _make_doc(doc_id: str, score: float, source: str = "slack") -> Document:
    doc = Document(
        page_content="테스트 문서 내용입니다.",
        metadata={
            "score": score,
            "title": f"Title {doc_id}",
            "source": source,
            "created_at": "2026-01-01T00:00:00Z",
        },
    )
    doc.id = doc_id
    return doc


def _make_reranked_doc(
    doc_id: str, relevance_score: float, source: str = "slack"
) -> Document:
    doc = Document(
        page_content="테스트 문서 내용입니다.",
        metadata={
            "relevance_score": relevance_score,
            "title": f"Title {doc_id}",
            "source": source,
            "created_at": "2026-01-01T00:00:00Z",
        },
    )
    doc.id = doc_id
    return doc


def test_search_probe_returns_pre_and_post_rerank():
    pre_docs = [_make_doc("doc1", 0.8), _make_doc("doc2", 0.6)]
    post_docs = [_make_reranked_doc("doc1", 0.95), _make_reranked_doc("doc2", 0.72)]

    mock_vector_service = MagicMock()
    mock_vector_service.hybrid_search_batch = AsyncMock(return_value=[pre_docs])

    mock_rerank_service = MagicMock()
    mock_rerank_service.rerank = AsyncMock(return_value=post_docs)

    with (
        patch(
            "catchup.server.debug.api.get_vector_db_service",
            return_value=mock_vector_service,
        ),
        patch(
            "catchup.server.debug.api.get_rerank_service",
            return_value=mock_rerank_service,
        ),
    ):
        response = client.post(
            "/api/v1/debug/search-probe",
            json={
                "rewritten_query": "배포 절차",
                "queries": ["배포 방법", "릴리즈 프로세스"],
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["query_count"] == 2
    assert data["pre_rerank_count"] == 2
    assert data["post_rerank_count"] == 2
    assert data["pre_rerank"][0]["doc_id"] == "doc1"
    assert data["pre_rerank"][0]["score"] == 0.8
    assert data["post_rerank"][0]["doc_id"] == "doc1"
    assert data["post_rerank"][0]["score"] == 0.95


def test_search_probe_passes_rewritten_query_to_reranker():
    pre_docs = [_make_doc("doc1", 0.7)]

    mock_vector_service = MagicMock()
    mock_vector_service.hybrid_search_batch = AsyncMock(return_value=[pre_docs])

    mock_rerank_service = MagicMock()
    mock_rerank_service.rerank = AsyncMock(
        return_value=[_make_reranked_doc("doc1", 0.9)]
    )

    with (
        patch(
            "catchup.server.debug.api.get_vector_db_service",
            return_value=mock_vector_service,
        ),
        patch(
            "catchup.server.debug.api.get_rerank_service",
            return_value=mock_rerank_service,
        ),
    ):
        client.post(
            "/api/v1/debug/search-probe",
            json={
                "rewritten_query": "배포 절차 문서",
                "queries": ["배포"],
            },
        )

    mock_rerank_service.rerank.assert_called_once()
    call_kwargs = mock_rerank_service.rerank.call_args
    assert call_kwargs.kwargs["query"] == "배포 절차 문서"


def test_search_probe_empty_results():
    mock_vector_service = MagicMock()
    mock_vector_service.hybrid_search_batch = AsyncMock(return_value=[[]])

    mock_rerank_service = MagicMock()
    mock_rerank_service.rerank = AsyncMock(return_value=[])

    with (
        patch(
            "catchup.server.debug.api.get_vector_db_service",
            return_value=mock_vector_service,
        ),
        patch(
            "catchup.server.debug.api.get_rerank_service",
            return_value=mock_rerank_service,
        ),
    ):
        response = client.post(
            "/api/v1/debug/search-probe",
            json={"rewritten_query": "존재하지 않는 내용", "queries": ["없는 쿼리"]},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["pre_rerank_count"] == 0
    assert data["post_rerank_count"] == 0
