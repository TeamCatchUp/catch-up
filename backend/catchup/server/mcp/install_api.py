from dataclasses import dataclass
from pathlib import Path

import structlog
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from fastapi.responses import Response
from jinja2 import Environment
from jinja2 import FileSystemLoader
from jinja2 import StrictUndefined

from catchup.auth.dependencies import get_current_user
from catchup.configs.config import auth_settings
from catchup.db.models import User

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/mcp", tags=["MCP Install"])

_SCRIPTS_DIR = Path(__file__).parent / "scripts"

_jinja_env = Environment(
    loader=FileSystemLoader(_SCRIPTS_DIR),
    undefined=StrictUndefined,
    keep_trailing_newline=True,
)


@dataclass(frozen=True)
class _PlatformConfig:
    template: str
    filename: str
    content_type: str


_PLATFORM_CONFIGS: dict[str, _PlatformConfig] = {
    "mac": _PlatformConfig(
        template="install_mac.sh.j2",
        filename="install-catchup-mcp.sh",
        content_type="text/x-shellscript; charset=utf-8",
    ),
    "windows": _PlatformConfig(
        template="install_windows.ps1.j2",
        filename="install-catchup-mcp.ps1",
        content_type="text/plain; charset=utf-8",
    ),
}


@router.get("/install/{platform}")
async def serve_install_script(
    platform: str,
    current_user: User = Depends(get_current_user),
) -> Response:
    """platform별 설치 스크립트를 렌더링해 반환한다."""
    config = _PLATFORM_CONFIGS.get(platform)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"지원하지 않는 플랫폼입니다: {platform}",
        )

    mcp_url = f"{auth_settings.FRONTEND_BASE_URL}/api/v1/mcp"
    content = _jinja_env.get_template(config.template).render(mcp_url=mcp_url)

    logger.info(
        "mcp_install_script_served",
        user_id=current_user.id,
        platform=platform,
    )

    return Response(
        content=content,
        media_type=config.content_type,
        headers={"Content-Disposition": f'attachment; filename="{config.filename}"'},
    )
