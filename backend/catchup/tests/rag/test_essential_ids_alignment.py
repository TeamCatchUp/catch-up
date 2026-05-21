"""
rerank alignment 버그 수정 테스트.

핵심 문제:
- ToolMessage가 매 iteration마다 [1]부터 리셋 → accumulated_docs 위치와 불일치
- 구 방식: extract_essential_ids(reasoning_xml, accumulated_docs)가 틀린 문서를 가리킴

수정:
- ToolMessage에 global index 적용 (existing_seen_count + newly_shown offset)
- map_indices_to_doc_ids → agent_seen_doc_ids 순서 기반 매핑 (submit_result 구조화 방식)
"""
from langchain_core.documents import Document

from catchup.rag.nodes.utils import build_docs_summary
from catchup.rag.nodes.utils import map_indices_to_doc_ids


def _doc(doc_id: str, content: str = "content") -> Document:
    return Document(page_content=content, metadata={"source": "slack"}, id=doc_id)


# ---------------------------------------------------------------------------
# build_docs_summary — start_index
# ---------------------------------------------------------------------------


def test_build_docs_summary_default_start_index():
    docs = [_doc("a"), _doc("b")]
    summary = build_docs_summary(docs)
    assert "[1] (slack)" in summary
    assert "[2] (slack)" in summary


def test_build_docs_summary_custom_start_index():
    """ToolMessage global index: iteration 1에서 5개 보여줬으면 iteration 2는 [6]부터."""
    docs = [_doc("d"), _doc("e")]
    summary = build_docs_summary(docs, start_index=6)
    assert "[6] (slack)" in summary
    assert "[7] (slack)" in summary
    assert "[1]" not in summary  # 리셋 없음


# ---------------------------------------------------------------------------
# map_indices_to_doc_ids (구 extract_essential_ids_from_agent_view 대체)
# ---------------------------------------------------------------------------


def test_extract_maps_to_agent_seen_order():
    """
    Global index 기반 매핑 검증.

    agent_seen_doc_ids = [A, B, C, D, E]  (노출 순서)
    accumulated_docs   = [D, A, B, C, E]  (삽입 순서, 다름!)

    key_document_indices: 1, 3  →  A, C  (agent_seen 순서 기준)
    기존 방식이면 D, B를 가리킴 → 버그
    """
    doc_a = _doc("id_A", "Release procedure doc A")
    doc_b = _doc("id_B", "Unrelated doc B")
    doc_c = _doc("id_C", "Release procedure doc C")
    doc_d = _doc("id_D", "Unrelated doc D")
    doc_e = _doc("id_E", "Unrelated doc E")

    # accumulated_docs: 최신 검색이 앞에 오는 삽입 순서
    accumulated_docs = [doc_d, doc_a, doc_b, doc_c, doc_e]

    # agent_seen_doc_ids: agent가 ToolMessage로 본 순서
    agent_seen_ids = ["id_A", "id_B", "id_C", "id_D", "id_E"]

    result = map_indices_to_doc_ids([1, 3], accumulated_docs, agent_seen_ids)

    # [1] = id_A, [3] = id_C (agent_seen 순서 기준)
    assert "id_A" in result
    assert "id_C" in result
    assert "id_D" not in result  # accumulated_docs[0]이지만 agent index [1]이 아님
    assert "id_B" not in result  # accumulated_docs[2]이지만 agent index [3]이 아님


def test_extract_global_index_across_iterations():
    """
    2회 검색 후 global index 연속성 검증.

    Iteration 1: ToolMessage → [1]=A, [2]=B, [3]=C
    Iteration 2: ToolMessage → [4]=D, [5]=E  (리셋 안 함)

    Agent stops: key_document_indices: 4, 5  →  D, E
    """
    doc_a = _doc("id_A")
    doc_b = _doc("id_B")
    doc_c = _doc("id_C")
    doc_d = _doc("id_D", "Release doc D")
    doc_e = _doc("id_E", "Release doc E")

    accumulated_docs = [doc_d, doc_e, doc_a, doc_b, doc_c]
    agent_seen_ids = ["id_A", "id_B", "id_C", "id_D", "id_E"]  # 노출 순서

    result = map_indices_to_doc_ids([4, 5], accumulated_docs, agent_seen_ids)

    assert "id_D" in result
    assert "id_E" in result
    assert "id_A" not in result


def test_extract_fallback_when_no_seen_ids():
    """agent_seen_ids가 비어있으면 accumulated_docs 순서로 fallback."""
    doc_a = _doc("id_A")
    doc_b = _doc("id_B")
    accumulated_docs = [doc_a, doc_b]

    result = map_indices_to_doc_ids([1], accumulated_docs, [])

    assert "id_A" in result


def test_extract_empty_when_no_indices():
    docs = [_doc("id_A")]
    result = map_indices_to_doc_ids([], docs, ["id_A"])
    assert result == set()


def test_extract_empty_when_no_docs():
    result = map_indices_to_doc_ids([1], [], [])
    assert result == set()
