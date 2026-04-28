from langchain_core.documents import Document

from catchup.rag.agents.tools.search_tools import _build_search_summary


def test_build_search_summary_limits_to_10_docs():
    """_build_search_summary가 최대 10개의 문서만 반환하는지 테스트"""
    docs = []
    for i in range(15):
        docs.append(Document(page_content=f"Content {i}", metadata={"source": "slack"}))

    summary = _build_search_summary("test query", docs)

    assert "결과 15건" in summary
    assert "[10]" in summary
    assert "[11]" not in summary


def test_build_search_summary_slices_confluence():
    """confluence 출처의 문서는 800자로 자르는지 테스트"""
    long_content = "A" * 1000
    docs = [
        Document(page_content=long_content, metadata={"source": "confluence"}),
        Document(page_content=long_content, metadata={"source": "slack"}),
    ]

    summary = _build_search_summary("test query", docs)

    lines = summary.split("\n")
    confluence_line = next(line for line in lines if "(confluence)" in line)
    slack_line = next(line for line in lines if "(slack)" in line)

    # confluence line snippet
    confluence_snippet_idx = lines.index(confluence_line) + 1
    confluence_snippet = lines[confluence_snippet_idx].strip()

    # slack line snippet
    slack_snippet_idx = lines.index(slack_line) + 1
    slack_snippet = lines[slack_snippet_idx].strip()

    assert len(confluence_snippet) == 800
    assert len(slack_snippet) == 1000
