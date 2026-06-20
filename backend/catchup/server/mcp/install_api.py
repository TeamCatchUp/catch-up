import uuid
from pathlib import Path

import structlog
from fastapi import APIRouter
from fastapi import Depends
from jinja2 import Environment
from jinja2 import FileSystemLoader
from jinja2 import StrictUndefined

from catchup.auth.dependencies import get_current_user
from catchup.db.models import User
from catchup.utils.redis import get_redis_client

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/mcp", tags=["MCP Install"])

_INSTALL_TOKEN_PREFIX = "mcp:install_token:"
_INSTALL_TOKEN_TTL = 600  # 10분

_SCRIPTS_DIR = Path(__file__).parent / "scripts"

_jinja_env = Environment(
    loader=FileSystemLoader(_SCRIPTS_DIR),
    undefined=StrictUndefined,
    keep_trailing_newline=True,
)


@router.post("/install/token")
async def issue_install_token(
    current_user: User = Depends(get_current_user),
) -> dict:
    """install token을 발급한다."""
    token = str(uuid.uuid4())
    redis = await get_redis_client()
    await redis.setex(
        f"{_INSTALL_TOKEN_PREFIX}{token}",
        _INSTALL_TOKEN_TTL,
        str(current_user.id),
    )
    logger.info(
        "mcp_install_token_issued", user_id=current_user.id, token=token
    )
    return {"token": token, "expires_in": _INSTALL_TOKEN_TTL}
