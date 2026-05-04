from langchain_core.documents import Document

from catchup.rag.nodes.utils import build_docs_summary


def test_build_docs_summary_dashboard_format():
    """build_docs_summary가 10개 문서를 제목 위주로 브리핑하고 나머지는 생략하는지 테스트"""
    docs = []
    for i in range(15):
        docs.append(
            Document(
                page_content=f"Content {i} is here to test", metadata={"source": "jira"}
            )
        )

    summary = build_docs_summary(docs)

    assert "총 15개 문서 누적됨" in summary
    assert "jira:15" in summary
    assert "[10]" in summary
    assert "[11]" not in summary
    assert "... 외 5개 문서가 더 메모리에 보관 중입니다." in summary


def test_build_docs_summary_short_snippet():
    """본문 스니펫이 50자로 잘리는지 테스트"""
    long_content = "A" * 100
    docs = [Document(page_content=long_content, metadata={"source": "slack"})]

    summary = build_docs_summary(docs)

    # 50자 자른 것 + "..."
    expected_snippet = "A" * 50 + "..."
    assert expected_snippet in summary
