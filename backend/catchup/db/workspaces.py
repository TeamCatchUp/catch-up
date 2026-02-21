    
from sqlalchemy import select
from sqlalchemy.orm import Session

from catchup.db.models import User, UserWorkspace, Workspace


def add_user_to_workspace(
    db: Session,
    user: User,
    workspace: Workspace
):
    user_workspace = UserWorkspace(
        user_id=user.id,
        workspace_id=workspace.id
    )
    db.add(user_workspace)
    
    
def get_workspace_by_id(
    db: Session,
    workspace_id: int
):
    stmt = (
        select(Workspace)
        .where(Workspace.id == workspace_id)
    )
    
    return db.scalar(stmt)