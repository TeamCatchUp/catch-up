import logging
from typing import Optional

from fastapi import APIRouter
from fastapi import Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import RedirectResponse

from catchup.configs.config import auth_settings
from catchup.db.engine import SessionLocal
from catchup.db.github import installation_repository as installation_crud

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/github", tags=["GitHub Connector"])


def _load_installation_account(installation_id: int) -> str | None:
    with SessionLocal() as db:
        installation = installation_crud.get_installation_by_installation_id(
            db,
            installation_id,
        )
        if installation is None:
            return None
        return installation.account_login


@router.get("/install")
async def github_app_install_callback(
    installation_id: Optional[int] = Query(None),
    setup_action: Optional[str] = Query(None),
):
    """
    GitHub App 설치 완료 후 Callback 엔드포인트

    GitHub App 설정에서 "Setup URL (optional)"로 등록:
    https://your-domain.com/api/v1/github/install

    GitHub이 전달하는 Query Parameters:
    - installation_id: 설치된 Installation ID
    - setup_action: "install" (신규 설치) 또는 "update" (권한 변경)
    """
    logger.info(
        f"GitHub App install callback received: "
        f"installation_id={installation_id}, setup_action={setup_action}"
    )

    if not installation_id:
        logger.warning("GitHub App install callback received without installation_id")
        redirect_url = f"{auth_settings.FRONTEND_REDIRECT_URI}?github_install=error&reason=missing_installation_id"
        return RedirectResponse(url=redirect_url)

    account_login = await run_in_threadpool(
        _load_installation_account,
        installation_id,
    )

    if account_login:
        logger.info(
            f"GitHub App installation found: "
            f"installation_id={installation_id}, account={account_login}"
        )
        redirect_url = (
            f"{auth_settings.FRONTEND_REDIRECT_URI}"
            f"?github_install=success"
            f"&installation_id={installation_id}"
            f"&account={account_login}"
        )
    else:
        logger.info(
            f"GitHub App installation not yet in DB: installation_id={installation_id}. "
            f"Webhook may arrive shortly."
        )
        redirect_url = (
            f"{auth_settings.FRONTEND_REDIRECT_URI}"
            f"?github_install=pending"
            f"&installation_id={installation_id}"
        )

    return RedirectResponse(url=redirect_url)
