from typing import Annotated
from typing import Literal
from typing_extensions import TypedDict


def _merge_node_results(old: dict, new: dict) -> dict:
    """노드 결과를 node_results에 머지하는 reducer."""
    return {**old, **new}


class WorkflowState(TypedDict):
    """LangGraph 실행 중 공유되는 워크플로우 상태.

    워크플로우 실행 흐름에 따른 node_results 누적 예시:

    # 초기 상태
    {
        "trigger": {"message": "환불 정책이 어떻게 되나요?", "channel_id": "ch-001"},
        "node_results": {},
    }

    # search 노드 실행 후
    {
        "trigger": {"message": "환불 정책이 어떻게 되나요?", "channel_id": "ch-001"},
        "node_results": {
            "search": {                     # node_id = "search"
                "query": "환불 정책이 어떻게 되나요?",
                "items": [{"id": "chunk-001", "content": "환불은 구매 후 7일 이내...", ...}],
                "total": 1,
            }
        },
    }

    # draft 노드 실행 후  ({{ node_results.search.items }} 로 search 결과를 참조)
    {
        "trigger": {...},
        "node_results": {
            "search": {...},
            "draft": {                      # node_id = "draft"
                "content": "안녕하세요. 환불 정책에 대해 안내드립니다...",
                "usage_metadata": {"input_tokens": 312, "output_tokens": 87},
            },
        },
    }
    """

    trigger: dict                                        # 웹훅 페이로드. 읽기 전용.
    node_results: Annotated[dict, _merge_node_results]   # 노드 실행 결과 누적. LangGraph가 머지.
    error: str | None
    status: Literal["in_progress", "completed", "error"]
