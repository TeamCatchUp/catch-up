from __future__ import annotations

from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from catchup.sync.common.schemas import FullSyncDispatchRequest
from catchup.sync.common.schemas import FullSyncRequestedTarget
from catchup.sync.common.schemas import SyncTargetType
from catchup.sync.full.resolvers.confluence import ConfluenceFullSyncTargetResolver
from catchup.sync.full.resolvers.github import GithubFullSyncTargetResolver


class MigratedConnectorResolverTests(IsolatedAsyncioTestCase):
    async def test_github_resolver_splits_repository_into_stream_targets(self) -> None:
        resolver = GithubFullSyncTargetResolver()
        request = FullSyncDispatchRequest(
            scope_id="123",
            targets=[
                FullSyncRequestedTarget(
                    target_type=SyncTargetType.REPOSITORY,
                    target_id="456",
                )
            ],
        )

        with (
            patch.object(resolver, "_load_installation_sync", return_value=object()),
            patch.object(
                resolver,
                "_load_repositories_sync",
                return_value=[
                    SimpleNamespace(repo_id=456, full_name="org/repo"),
                ],
            ),
        ):
            resolved = await resolver.resolve_full_sync_targets(request=request)

        self.assertEqual(len(resolved.targets), 2)
        self.assertEqual(
            [target.metadata["stream_type"] for target in resolved.targets],
            ["issue", "pull_request"],
        )
        self.assertEqual(
            [target.metadata["repo_full_name"] for target in resolved.targets],
            ["org/repo", "org/repo"],
        )

    async def test_confluence_resolver_splits_space_into_content_targets(self) -> None:
        resolver = ConfluenceFullSyncTargetResolver()
        request = FullSyncDispatchRequest(
            scope_id="cloud-123",
            targets=[
                FullSyncRequestedTarget(
                    target_type=SyncTargetType.SPACE,
                    target_id="ENG",
                )
            ],
        )

        with (
            patch.object(resolver, "_load_token_sync", return_value=object()),
            patch.object(
                resolver,
                "_load_spaces_sync",
                return_value=[
                    SimpleNamespace(space_key="ENG", space_name="Engineering"),
                ],
            ),
        ):
            resolved = await resolver.resolve_full_sync_targets(request=request)

        self.assertEqual(len(resolved.targets), 2)
        self.assertEqual(
            [target.metadata["content_type"] for target in resolved.targets],
            ["page", "blogpost"],
        )
        self.assertEqual(
            [target.metadata["space_name"] for target in resolved.targets],
            ["Engineering", "Engineering"],
        )
