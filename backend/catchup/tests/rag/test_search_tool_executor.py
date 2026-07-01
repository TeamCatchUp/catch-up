from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from langchain_core.documents import Document
from langchain_core.messages import AIMessage

from catchup.rag.agents.tools.search_tools import search_tool_executor_node


@pytest.mark.asyncio
async def test_search_tool_executor_node_merge_strategy():
    """최신 검색 결과(new_unique)가 기존 accumulated_docs 앞에 위치하는지 테스트"""

    existing_docs = [
        Document(page_content="Old 1", metadata={"source": "slack"}, id="old1"),
        Document(page_content="Old 2", metadata={"source": "confluence"}, id="old2"),
    ]

    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "single_query_search",
                        "args": {"query": "test"},
                        "id": "call_1",
                    }
                ],
            )
        ],
        "accumulated_docs": existing_docs,
        "tool_filters": [],
    }

    mock_vector_db = MagicMock()

    new_docs = [
        Document(page_content="New 1", metadata={"source": "slack"}, id="new1"),
        # existing doc id="old1"가 다시 검색되었다고 가정 (중복 제거되어야 함)
        Document(page_content="Old 1", metadata={"source": "slack"}, id="old1"),
    ]

    # _run_search를 모킹하여 새 문서를 반환하도록 설정
    with patch(
        "catchup.rag.agents.tools.search_tools._run_search", new_callable=AsyncMock
    ) as mock_run_search:
        mock_run_search.return_value = (new_docs, "summary")

        result = await search_tool_executor_node(state, mock_vector_db)

        merged_docs = result["accumulated_docs"]

        # 총 문서는 3개여야 함 (새로운 1개 + 기존 2개) - old1은 중복 제거
        assert len(merged_docs) == 3

        # 최신 문서가 맨 앞에 와야 함
        assert merged_docs[0].id == "new1"
        assert merged_docs[1].id == "old1"
        assert merged_docs[2].id == "old2"
