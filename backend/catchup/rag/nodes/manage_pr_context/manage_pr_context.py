import asyncio
import logging
from typing import Any

from langgraph.types import interrupt

from catchup.components.connectors.github.factory import get_github_service
from catchup.rag.schemas import (
    PullRequestCandidate,
    PullRequestUserSelected,
)
from catchup.rag.state import AgentState
from catchup.search.schemas import BaseSearchResult, PullRequestSearchResult, SourceType

logger = logging.getLogger(__name__)


async def manage_pr_context_node(state: AgentState):
    logger.info("manage_pr_context node 진입")

    github_service = get_github_service()

    retrieved_docs: list[BaseSearchResult] = state.get("retrieved_docs", [])  # truth

    pr_docs: list[PullRequestSearchResult] = [
        doc for doc in retrieved_docs if doc.source_type == SourceType.PULL_REQUEST
    ]

    if not pr_docs:
        logger.info("Skip: PR 관련 문서 없음")
        return {"retrieved_docs": retrieved_docs}

    target_prs: list[PullRequestSearchResult] = []

    if len(pr_docs) == 1:
        logger.info(f"PR 1개 발견. 자동 선택 - [#{pr_docs[0].pr_number}]")
        target_prs = [pr_docs[0]]

    else:
        logger.info(f"PR {len(pr_docs)}개 발견. 사용자 선택 요청 (Interrupt)")

        candidates: list[dict[str, Any]] = [
            PullRequestCandidate.from_search_result_doc(doc).model_dump()
            for doc in pr_docs
        ]

        user_selected_prs: list[PullRequestUserSelected] = interrupt(candidates)
        logger.info(f"사용자 선택 완료: {len(user_selected_prs)} 개")

        if not user_selected_prs:
            logger.info("Skip: 사용자가 선택한 PR이 없음.")
            return {"retrieved_docs": retrieved_docs}

        selected_pr_numbers = {item.pr_number for item in user_selected_prs}

        target_prs: list[PullRequestSearchResult] = [
            pr for pr in pr_docs if pr.pr_number in selected_pr_numbers
        ]

    tasks = [
        github_service.get_pr_context(pr.owner, pr.repo, pr.pr_number)
        for pr in target_prs
    ]

    results = await asyncio.gather(*tasks)

    for pr, context_data in zip(target_prs, results):
        pr.file_context = context_data
        logger.info(
            f"PR #{pr.pr_number} 컨텍스트 업데이트 완료 ({len(context_data)} 파일)"
        )

    return {"retrieved_docs": retrieved_docs}
