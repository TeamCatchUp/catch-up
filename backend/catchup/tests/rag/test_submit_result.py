from langchain_core.documents import Document

from catchup.rag.agents.tools.search_tools import REACT_TOOLS
from catchup.rag.nodes.utils import map_indices_to_doc_ids


def _doc(doc_id: str) -> Document:
    return Document(page_content="content", metadata={"source": "github"}, id=doc_id)


def test_submit_result_in_react_tools():
    names = [t.name for t in REACT_TOOLS]
    assert "submit_result" in names


def test_submit_result_schema_has_required_fields():
    tool = next(t for t in REACT_TOOLS if t.name == "submit_result")
    schema = tool.args_schema.schema()
    props = schema["properties"]
    assert "key_document_indices" in props
    assert "key_documents" in props
    assert "search_coverage" in props
    assert "reason_for_stopping" in props


def test_map_indices_to_doc_ids_basic():
    docs = [_doc("id_A"), _doc("id_B"), _doc("id_C")]
    result = map_indices_to_doc_ids([1, 3], docs, [])
    assert result == {"id_A", "id_C"}


def test_map_indices_to_doc_ids_uses_agent_seen_order():
    """agent_seen_ids 순서 기준으로 매핑해야 한다 (accumulated_docs 삽입 순서 아님)."""
    doc_a = _doc("id_A")
    doc_b = _doc("id_B")
    doc_c = _doc("id_C")
    accumulated = [doc_c, doc_a, doc_b]        # 삽입 순서
    agent_seen = ["id_A", "id_B", "id_C"]      # 노출 순서
    result = map_indices_to_doc_ids([1, 2], accumulated, agent_seen)
    assert result == {"id_A", "id_B"}          # seen 순서 기준 [1]=A, [2]=B


def test_map_indices_out_of_range_ignored():
    docs = [_doc("id_A")]
    result = map_indices_to_doc_ids([1, 99], docs, [])
    assert result == {"id_A"}  # 99 무시


def test_map_indices_empty():
    assert map_indices_to_doc_ids([], [], []) == set()
