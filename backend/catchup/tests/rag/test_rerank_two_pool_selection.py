# backend/catchup/tests/rag/test_rerank_two_pool_selection.py
import pytest
from langchain_core.documents import Document

from catchup.rag.nodes.rerank.final_doc_selection import _apply_two_pool_selection
from catchup.rag.nodes.utils import get_document_id


def _doc(doc_id: str, score: float = 0.5) -> Document:
    return Document(
        page_content=f"content {doc_id}",
        metadata={"relevance_score": score, "source": "test"},
        id=doc_id,
    )


def _ids(docs: list[Document]) -> list[str]:
    return [get_document_id(d) for d in docs]


# ---------------------------------------------------------------------------
# Pool selection correctness
# ---------------------------------------------------------------------------


def test_cut_off_essential_enters_pool_b():
    """reranker가 cut-off한 essential 문서가 pool B를 통해 final_docs에 포함된다."""
    reranked = [_doc(f"r{i}", score=1.0 - i * 0.05) for i in range(15)]
    essential_doc = _doc("e1", score=0.25)
    reranked.append(essential_doc)

    final_docs, metadata = _apply_two_pool_selection(
        reranked_docs=reranked,
        essential_doc_ids={"e1"},
        total_k=10,
    )

    assert "e1" in _ids(final_docs)
    assert len(final_docs) == 10


def test_essential_already_in_top_k_no_bypass():
    """essential 문서가 reranker top-K에 이미 있으면 pool B가 비어 있다."""
    reranked = [_doc(f"r{i}", score=1.0 - i * 0.05) for i in range(5)]
    essential_doc_ids = {"r0"}

    final_docs, metadata = _apply_two_pool_selection(
        reranked_docs=reranked,
        essential_doc_ids=essential_doc_ids,
        total_k=5,
    )

    assert metadata["bypass_count"] == 0
    assert metadata["cut_off_essential_count"] == 0
    assert metadata["reranker_essential_recall"] == 1.0
    assert _ids(final_docs) == _ids(reranked[:5])


def test_cut_off_exceeds_budget_sorted_by_score():
    """cut_off_essential이 essential_budget을 초과하면 rerank score 높은 순으로 자른다."""
    reranked = [_doc(f"r{i}", score=1.0 - i * 0.05) for i in range(10)]
    e_high = _doc("e_high", score=0.35)
    e_mid1 = _doc("e_mid1", score=0.30)
    e_mid2 = _doc("e_mid2", score=0.25)
    e_low1 = _doc("e_low1", score=0.20)
    e_low2 = _doc("e_low2", score=0.15)
    reranked.extend([e_high, e_mid1, e_mid2, e_low1, e_low2])

    essential_doc_ids = {"e_high", "e_mid1", "e_mid2", "e_low1", "e_low2"}

    final_docs, metadata = _apply_two_pool_selection(
        reranked_docs=reranked,
        essential_doc_ids=essential_doc_ids,
        total_k=10,
    )

    assert metadata["bypass_budget"] == 3
    assert metadata["bypass_count"] == 3
    assert metadata["cut_off_essential_count"] == 5
    assert "e_high" in _ids(final_docs)
    assert "e_mid1" in _ids(final_docs)
    assert "e_mid2" in _ids(final_docs)
    assert "e_low1" not in _ids(final_docs)
    assert "e_low2" not in _ids(final_docs)
    assert len(final_docs) == 10


def test_empty_essential_pure_reranker():
    """essential_doc_ids가 비어 있으면 pool B가 없고 reranker가 total_k 전부 채운다."""
    reranked = [_doc(f"r{i}", score=1.0 - i * 0.05) for i in range(20)]

    final_docs, metadata = _apply_two_pool_selection(
        reranked_docs=reranked,
        essential_doc_ids=set(),
        total_k=15,
    )

    assert len(final_docs) == 15
    assert metadata["bypass_count"] == 0
    assert metadata["reranker_essential_recall"] == 0.0


def test_total_never_exceeds_k():
    """어떤 경우에도 final_docs 수는 total_k를 초과하지 않는다."""
    reranked = [_doc(f"r{i}", score=1.0 - i * 0.02) for i in range(50)]
    essential_doc_ids = {f"r{i}" for i in range(25, 50)}

    for total_k in [10, 15, 20]:
        final_docs, _ = _apply_two_pool_selection(
            reranked_docs=reranked,
            essential_doc_ids=essential_doc_ids,
            total_k=total_k,
        )
        assert len(final_docs) <= total_k


def test_empty_reranked_docs():
    """reranked_docs가 비어 있으면 빈 리스트와 기본 metadata를 반환한다."""
    final_docs, metadata = _apply_two_pool_selection(
        reranked_docs=[],
        essential_doc_ids={"e1"},
        total_k=10,
    )
    assert final_docs == []
    assert metadata["bypass_count"] == 0


# ---------------------------------------------------------------------------
# Metadata correctness
# ---------------------------------------------------------------------------


def test_global_metadata_fields_present():
    """반환 metadata에 4개의 global 필드가 모두 포함된다."""
    reranked = [_doc(f"r{i}", score=1.0 - i * 0.1) for i in range(5)]
    _, metadata = _apply_two_pool_selection(
        reranked_docs=reranked,
        essential_doc_ids=set(),
        total_k=5,
    )
    assert "reranker_essential_recall" in metadata
    assert "cut_off_essential_count" in metadata
    assert "bypass_count" in metadata
    assert "bypass_budget" in metadata


def test_per_doc_metadata_reranker_pool():
    """Pool A 문서의 per-doc metadata가 올바르게 설정된다."""
    reranked = [_doc(f"r{i}", score=1.0 - i * 0.1) for i in range(5)]

    final_docs, _ = _apply_two_pool_selection(
        reranked_docs=reranked,
        essential_doc_ids=set(),
        total_k=5,
    )

    for doc in final_docs:
        assert "original_rerank_score" in doc.metadata
        assert "is_agent_essential" in doc.metadata
        assert "reranker_rank" in doc.metadata
        assert doc.metadata["selection_pool"] == "reranker"


def test_per_doc_metadata_bypass_pool():
    """Pool B 문서의 selection_pool이 'essential_bypass'이고 reranker_rank가 top_k보다 크다."""
    reranked = [_doc(f"r{i}", score=1.0 - i * 0.05) for i in range(12)]
    essential_doc = _doc("e1", score=0.20)
    reranked.append(essential_doc)

    final_docs, _ = _apply_two_pool_selection(
        reranked_docs=reranked,
        essential_doc_ids={"e1"},
        total_k=10,
    )

    bypass_docs = [d for d in final_docs if d.metadata["selection_pool"] == "essential_bypass"]
    assert len(bypass_docs) == 1
    assert get_document_id(bypass_docs[0]) == "e1"
    assert bypass_docs[0].metadata["reranker_rank"] > 10
    assert bypass_docs[0].metadata["is_agent_essential"] is True


def test_reranker_essential_recall_calculation():
    """reranker_essential_recall = essential ∩ top-K / essential 총 수."""
    top5 = [_doc(f"r{i}", score=1.0 - i * 0.1) for i in range(5)]
    top5[0] = _doc("e1", score=0.95)
    top5[2] = _doc("e2", score=0.75)
    below = [_doc(f"b{i}", score=0.3 - i * 0.05) for i in range(5)]
    below[0] = _doc("e3", score=0.28)
    below[1] = _doc("e4", score=0.25)
    reranked = top5 + below

    _, metadata = _apply_two_pool_selection(
        reranked_docs=reranked,
        essential_doc_ids={"e1", "e2", "e3", "e4"},
        total_k=5,
    )

    assert metadata["reranker_essential_recall"] == pytest.approx(0.5)
    assert metadata["cut_off_essential_count"] == 2


def test_essential_budget_values():
    """total_k별 essential_budget = floor(total_k * 0.3)."""
    reranked = [_doc(f"r{i}", score=1.0 - i * 0.01) for i in range(100)]

    for total_k, expected_budget in [(10, 3), (15, 4), (20, 6)]:
        _, metadata = _apply_two_pool_selection(
            reranked_docs=reranked,
            essential_doc_ids=set(),
            total_k=total_k,
        )
        assert metadata["bypass_budget"] == expected_budget
