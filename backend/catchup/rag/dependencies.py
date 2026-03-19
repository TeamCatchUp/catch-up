from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from sqlalchemy.orm import Session

from catchup.auth.dependencies import get_current_user
from catchup.db.dependencies import get_db
from catchup.db.models import User
from catchup.db.users import get_user_with_full_context
from catchup.rag.schemas.context import GlobalCompanyContext
from catchup.rag.schemas.context import GlobalContext
from catchup.rag.schemas.context import GlobalUserContext
from catchup.rag.schemas.context import GlobalWorkspaceContext


async def get_rag_global_context(
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db),
) -> GlobalContext:
    
    db_user_full = get_user_with_full_context(db_session, current_user.id)
    
    if not db_user_full:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="User context not found"
        )
    
    if not db_user_full.workspace_links:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not belong to any workspace"
        )
        
    # TODO: 향후 클라이언트에서 전달받은 workspace_id로 매칭하는 로직 추가
    target_workspace = db_user_full.workspace_links[0].workspace
    
    if not target_workspace.company:
         raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Company context not found for this workspace"
        )

    return GlobalContext(
        user=GlobalUserContext.model_validate(db_user_full),
        workspace=GlobalWorkspaceContext.model_validate(target_workspace),
        company=GlobalCompanyContext.model_validate(target_workspace.company),
    )