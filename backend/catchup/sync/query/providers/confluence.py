from __future__ import annotations

from fastapi.concurrency import run_in_threadpool

from catchup.connectors.atlassian.oauth_client import AtlassianOAuthClient
from catchup.connectors.atlassian.token_manager import AtlassianTokenManager
from catchup.connectors.confluence.metadata_service import ConfluenceMetadataService
from catchup.db.atlassian import oauth_repository as atlassian_oauth_repository
from catchup.db.engine import SessionLocal
from catchup.db.models import AtlassianOAuthToken
from catchup.db.models import SyncConnector
from catchup.sync.query.providers.common import build_targets_result
from catchup.sync.query.types import SyncTargetResult
from catchup.sync.query.types import SyncTargetsResult


def _load_confluence_token_db(scope_id: str) -> AtlassianOAuthToken | None:
    with SessionLocal() as db:
        return (
            db.query(AtlassianOAuthToken)
            .filter(AtlassianOAuthToken.cloud_id == scope_id)
            .first()
        )


async def list_confluence_targets(*, scope_id: str) -> SyncTargetsResult:
    token = await run_in_threadpool(_load_confluence_token_db, scope_id)
    if token is None:
        raise ValueError(f"confluence cloud is not connected: {scope_id}")

    token_manager = AtlassianTokenManager(
        oauth_client=AtlassianOAuthClient(),
        oauth_repository=atlassian_oauth_repository,
    )
    metadata_service = ConfluenceMetadataService(token_manager)
    spaces = await metadata_service.sync_space_snapshot(
        scope_id,
        granted_scopes=set((token.scopes or "").split()),
    )

    targets = [
        SyncTargetResult(
            target_id=space["space_key"],
            display_name=space["space_name"] or space["space_key"],
            target_type="space",
            is_accessible=True,
            metadata={
                "space_key": space["space_key"],
                "space_id": str(space["space_id"]),
            },
        )
        for space in ([] if spaces is None else spaces)
        if space["space_key"]
    ]
    return build_targets_result(
        connector=SyncConnector.CONFLUENCE,
        scope_id=scope_id,
        targets=targets,
    )
