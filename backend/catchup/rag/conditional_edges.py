import logging

from catchup.rag.state import AgentState

logger = logging.getLogger(__name__)

def route_question(state: AgentState):
    intent = state["intent"]
    if intent == "chitchat":
        return "chitchat"
    elif intent == "search_pipeline":
        return "rewrite"


def route_after_rerank(state: AgentState):
    mode = state.get("mode", "standard")
    if mode == "fast":
        return "generate_final_answer_fast"
    retry_count = state.get("retry_count", 0)
    if retry_count >= 1:
        return "generate_final_answer"
    return "grade"


def route_after_grade(state: AgentState):
    status = state.get("grade_status")
    retry_count = state.get("retry_count", 0)
    
    if status == "bad" and retry_count < 2:
        return "rewrite"
    
    # if retry_count >= 2:
    #     logger.info("Vector Search 최대 재시도 횟수 도달. Graph Search 전략 선택.")
        
    #     anchor_ids = extract_anchor_ids(state.get("retrieved_docs", []))
        
    #     if anchor_ids:
    #         logger.info(f"Anchor 발견 {len(anchor_ids)} 개 -> expand_graph_context 노드로 이동.")
    #         return "expand_graph_context"
        
    #     else:
    #         logger.info("Anchor 없음 -> fallback_cypher_query 노드로 이동.")
    #         return "fallback_cypher_query"
    
    return "generate_final_answer"
