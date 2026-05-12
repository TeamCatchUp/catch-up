from functools import partial

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END
from langgraph.graph import StateGraph
from langgraph.types import RetryPolicy

from catchup.components.llm.factory import LlmProvider
from catchup.components.llm.factory import ModelCapacity
from catchup.components.llm.factory import get_llm_service
from catchup.rag.retryable import RETRYABLE_ERRORS
from catchup.search.planner.plan_manual_search import plan_manual_search_node
from catchup.search.planner.state import ManualSearchState


def get_search_planner_graph(
    checkpointer: BaseCheckpointSaver | None = None,
):
    llm_small = get_llm_service(
        LlmProvider.AWS_BEDROCK,
        ModelCapacity.SMALL,
        streaming=False,
        isolated=True,
        max_attempts=0,
    ).get_llm()

    workflow = StateGraph(ManualSearchState)
    workflow.add_node(
        "plan_manual_search_node",
        partial(plan_manual_search_node, llm=llm_small, timeout=10.0),
        retry=RetryPolicy(
            retry_on=RETRYABLE_ERRORS,
            max_attempts=2,
            initial_interval=1.0,
            backoff_factor=2.0,
        ),
    )
    workflow.set_entry_point("plan_manual_search_node")
    workflow.add_edge("plan_manual_search_node", END)

    return workflow.compile(checkpointer=checkpointer)
