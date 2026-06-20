import uuid
from pathlib import Path

import structlog
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi import status
from fastapi.responses import Response
from jinja2 import Environment
from jinja2 import FileSystemLoader
from jinja2 import StrictUndefined

from catchup.auth.dependencies import get_current_user
from catchup.configs.config import auth_settings
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


_PLATFORM_MAC = "mac"
_PLATFORM_WINDOWS = "windows"

_SCRIPT_TEMPLATES = {
    _PLATFORM_MAC: "install_mac.sh.j2",
    _PLATFORM_WINDOWS: "install_windows.ps1.j2",
}

_SCRIPT_FILENAMES = {
    _PLATFORM_MAC: "install-catchup-mcp.sh",
    _PLATFORM_WINDOWS: "install-catchup-mcp.ps1",
}

_SCRIPT_CONTENT_TYPES = {
    _PLATFORM_MAC: "text/x-shellscript; charset=utf-8",
    _PLATFORM_WINDOWS: "text/plain; charset=utf-8",
}


async def _verify_and_consume_install_token(token: str) -> None:
    """install token을 검증하고 소비한다. 유효하지 않으면 401을 발생시킨다."""
    # get_redis_client()는 싱글턴을 반환한다. 호출자와 중복 호출해도 연결 비용이 없다.
    redis = await get_redis_client()
    result = await redis.getdel(f"{_INSTALL_TOKEN_PREFIX}{token}")
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="설치 링크가 만료되었거나 이미 사용되었습니다. 다시 생성해 주세요.",
        )


@router.get("/install/{platform}")
async def serve_install_script(
    platform: str,
    token: str = Query(...),
) -> Response:
    """platform별 설치 스크립트를 렌더링해 반환한다."""
    # 플랫폼 검증을 토큰 소비보다 먼저 수행한다.
    # 순서가 바뀌면 유효하지 않은 플랫폼 요청에도 토큰이 소비된다.
    if platform not in _SCRIPT_TEMPLATES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"지원하지 않는 플랫폼입니다: {platform}",
        )

    await _verify_and_consume_install_token(token)

    mcp_url = f"{auth_settings.FRONTEND_BASE_URL}/api/v1/mcp"
    template = _jinja_env.get_template(_SCRIPT_TEMPLATES[platform])
    content = template.render(mcp_url=mcp_url)

    filename = _SCRIPT_FILENAMES[platform]
    return Response(
        content=content,
        media_type=_SCRIPT_CONTENT_TYPES[platform],
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )
