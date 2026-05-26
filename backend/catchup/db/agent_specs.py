from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload

from catchup.db.models import User
from catchup.db.models import Workspace
from catchup.rag.schemas.context import GlobalCompanyContext
from catchup.rag.schemas.context import GlobalContext
from catchup.rag.schemas.context import GlobalUserContext
from catchup.rag.schemas.context import GlobalWorkspaceContext


def build_agent_global_context(
    db: Session,
    workspace_id: int,
    user_id: int,
) -> GlobalContext:
    """AgentSpec의 workspace_id/user_id로 GlobalContext를 구성한다.

    에이전트는 항상 고정 user에 귀속되므로 매 실행마다 동일한 컨텍스트를 반환한다.
    """
    user = db.scalar(select(User).where(User.id == user_id))
    workspace = db.scalar(
        select(Workspace)
        .where(Workspace.id == workspace_id)
        .options(joinedload(Workspace.company))
    )

    if user is None:
        raise ValueError(f"User not found: user_id={user_id}")
    if workspace is None:
        raise ValueError(f"Workspace not found: workspace_id={workspace_id}")

    return GlobalContext(
        user=GlobalUserContext(
            id=user.id,
            name=user.name,
            email=user.email,
            department=user.department,
        ),
        workspace=GlobalWorkspaceContext(
            id=workspace.id,
            name=workspace.name,
        ),
        company=GlobalCompanyContext(
            id=workspace.company.id,
            name=workspace.company.name,
            description=workspace.company.description or "",
        ),
    )
