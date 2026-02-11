from fastapi import Depends

from catchup.auth.dependencies import get_current_user
from catchup.db.models import User
from catchup.rag.schemas.context import GlobalContext, GlobalUserContext

# TODO: company 정보 등 채울 게 많음
async def get_full_global_context(
    db_user: User = Depends(get_current_user),
) -> GlobalContext:
        
    user_context = GlobalUserContext.from_db_user(db_user)

    # --- [최종 조립] ---
    return GlobalContext(
        user=user_context
        # company=company_ctx
    )