"""LLM Wiki 소스 타입의 검색 노출 화이트리스트를 검증한다."""

from langchain_core.documents import Document

from catchup.db.models import SourceType
from catchup.schemas.filters import CREATED_AT_TOOLS
from catchup.schemas.filters import UPDATED_AT_TOOLS
from catchup.schemas.sources import SOURCE_METADATA
from catchup.schemas.sources import BaseSource


def test_llm_wiki_source_type_exists() -> None:
    assert SourceType.LLM_WIKI.value == "llm_wiki"


def test_llm_wiki_in_created_at_tools() -> None:
    # 날짜 필터 검색의 화이트리스트에서 빠지면 조용히 누락된다.
    assert SourceType.LLM_WIKI in CREATED_AT_TOOLS
    assert SourceType.LLM_WIKI not in UPDATED_AT_TOOLS


def test_llm_wiki_has_source_metadata() -> None:
    # SOURCE_METADATA에서 빠지면 LLM 프롬프트에 role/authority가
    # 주입되지 않는다.
    assert SourceType.LLM_WIKI in SOURCE_METADATA


def test_from_document_builds_llm_wiki_source() -> None:
    doc = Document(
        id="llm_wiki:artifact_revision:a1:heading:0",
        page_content="캐치업 오픈 API — rate_limit_per_minute: 60",
        metadata={
            "source": "llm_wiki",
            "entity_type": "artifact_revision",
            "artifact_id": "a1",
            "title": "캐치업 오픈 API",
            "heading": "rate_limit_per_minute",
            "contextual_content": (
                "캐치업 오픈 API — rate_limit_per_minute: 60"
            ),
        },
    )

    source = BaseSource.from_document(index=1, doc=doc)

    assert source.source == SourceType.LLM_WIKI
    assert source.title == "캐치업 오픈 API"
    assert source.artifact_id == "a1"
    assert source.heading == "rate_limit_per_minute"
    assert source.text == "캐치업 오픈 API — rate_limit_per_minute: 60"
