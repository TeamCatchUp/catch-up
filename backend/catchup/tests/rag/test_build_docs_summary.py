from langchain_core.documents import Document

from catchup.rag.nodes.utils import build_docs_summary


def _doc(content: str, source: str) -> Document:
    return Document(page_content=content, metadata={"source": source}, id="x")


def test_confluence_truncated_at_500():
    long_content = "A" * 600
    doc = _doc(long_content, "confluence")
    summary = build_docs_summary([doc])
    assert "A" * 500 in summary
    assert "A" * 501 not in summary
    assert "..." in summary


def test_channel_talk_truncated_at_500():
    long_content = "B" * 600
    doc = _doc(long_content, "channel_talk")
    summary = build_docs_summary([doc])
    assert "B" * 500 in summary
    assert "B" * 501 not in summary


def test_github_not_truncated():
    long_content = "C" * 600
    doc = _doc(long_content, "github")
    summary = build_docs_summary([doc])
    assert "C" * 600 in summary
    assert "..." not in summary


def test_slack_not_truncated():
    long_content = "D" * 600
    doc = _doc(long_content, "slack")
    summary = build_docs_summary([doc])
    assert "D" * 600 in summary


def test_jira_not_truncated():
    long_content = "E" * 600
    doc = _doc(long_content, "jira")
    summary = build_docs_summary([doc])
    assert "E" * 600 in summary


def test_short_confluence_not_truncated():
    doc = _doc("짧은 내용", "confluence")
    summary = build_docs_summary([doc])
    assert "..." not in summary
