from catchup.rag.nodes.utils import log_node
from catchup.rag.state import AgentState


@log_node
async def search_graph_db_node(state: AgentState):
    return {"retrieved_docs": state["retrieved_docs"]}