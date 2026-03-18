import asyncio

import structlog
from catchup.observability.langfuse.configs import get_langfuse_client

logger = structlog.get_logger()

SCORE_NAME = "user_feedback"

def _get_score_id(trace_id: str) -> str:
    # 같은 trace에 중복 score가 생기는 것을 방지한다.
    return f"{trace_id}-{SCORE_NAME}"

async def upsert_feedback(
    trace_id: str,
    content: dict,
):
    if not trace_id:
        return
    
    langfuse_client = get_langfuse_client()
    if not langfuse_client:
        return
    
    is_liked = content.get("is_liked")
    reasons = content.get("reasons") or []
    comment = content.get("comment")
    score_id = _get_score_id(trace_id)
    
    try:
        if is_liked is None:
            def _delete_sync():
                langfuse_client.api.score.delete(score_id=score_id)
            
            await asyncio.to_thread(_delete_sync)
            logger.info(
                "langfuse_user_feedback_deleted",
                trace_id=trace_id
            )

        else:
            def _upsert_sync():
                langfuse_client.create_score(
                    score_id=score_id,
                    name=SCORE_NAME,
                    trace_id=trace_id,
                    value=is_liked,
                    data_type="BOOLEAN",
                    metadata=reasons,
                    comment=comment
                )
        
            await asyncio.to_thread(_upsert_sync)

        logger.info(
            "langfuse_user_feedback_upserted",
            trace_id=trace_id,
            is_liked=is_liked
        )
    
    except Exception as e:
        logger.error(
            "langfuse_user_feedback_failed",
            trace_id=trace_id,
            error=str(e)
        )