from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from catchup.auth.dependencies import get_current_user
from catchup.db.dependencies import get_db
from catchup.db.models import User
from catchup.db.users import get_user_with_full_context
from catchup.rag.schemas.context import GlobalCompanyContext, GlobalContext, GlobalUserContext, GlobalWorkspaceContext


async def get_rag_global_context(
    authorized_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db),
) -> GlobalContext:
    
    db_user_full = get_user_with_full_context(db_session, authorized_user.id)
    
    if not db_user_full:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="User context not found"
        )
    
    user_context = GlobalUserContext.from_db_user(db_user_full)
    company_context = _extract_company_context(db_user_full)
    workspace_context = _extract_workspace_context(db_user_full)
    
    return GlobalContext(
        user=user_context,
        workspace=workspace_context,
        company=company_context
    )

def _extract_company_context(user: User) -> GlobalCompanyContext:
    """User로부터 Company 정보를 추출하는 과정"""
    if user.workspace_links:
        workspace = user.workspace_links[0].workspace  # TODO: workspace가 늘어날 경우 [0] 수정 필요
        if workspace.company:
            return GlobalCompanyContext.from_db_company(workspace.company)
            
    # Fallback
    return GlobalCompanyContext(
        id=0, 
        name="Unknown", 
        description="No company context available"
    )

def _extract_workspace_context(user: User) -> GlobalWorkspaceContext:
    """User로부터 Workspace 정보를 추출하는 과정"""
    if user.workspace_links:
        workspace = user.workspace_links[0].workspace
        return GlobalWorkspaceContext(
            id=workspace.id,
            name=workspace.name
        )
    
    # Fallback
    return GlobalWorkspaceContext(
        id=0,
        name="Default Workspace" 
    )