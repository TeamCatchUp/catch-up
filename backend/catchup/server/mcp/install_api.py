from pathlib import Path

import structlog
from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import status
from fastapi.responses import Response
from jinja2 import Environment
from jinja2 import FileSystemLoader
from jinja2 import StrictUndefined

from catchup.configs.config import auth_settings

logger = structlog.get_logger()

router = APIRouter(prefix="/api/v1/mcp", tags=["MCP Install"])

_SCRIPTS_DIR = Path(__file__).parent / "scripts"

_jinja_env = Environment(
    loader=FileSystemLoader(_SCRIPTS_DIR),
    undefined=StrictUndefined,
    keep_trailing_newline=True,
)

_SCRIPT_CONFIGS = {
    "mac": ("install_mac.command.j2", "text/x-shellscript; charset=utf-8"),
    "windows": ("install_windows.ps1.j2", "text/plain; charset=utf-8"),
}


@router.get("/script/{platform}", include_in_schema=False)
async def serve_install_script(platform: str) -> Response:
    """curl/irm으로 직접 실행하는 설치 스크립트를 반환한다."""
    config = _SCRIPT_CONFIGS.get(platform)
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"지원하지 않는 플랫폼입니다: {platform}",
        )

    template_name, content_type = config
    mcp_url = f"{auth_settings.FRONTEND_BASE_URL}/api/v1/mcp/"
    content = _jinja_env.get_template(template_name).render(mcp_url=mcp_url)

    logger.info("mcp_install_script_served", platform=platform)

    return Response(content=content, media_type=content_type)
