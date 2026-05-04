from __future__ import annotations

from collections.abc import Callable

from catchup.connector_core.ports.connection_status import ConnectionStatus
from catchup.connector_core.ports.connection_status import ConnectionStatusItem
from catchup.connector_core.ports.connection_status import ConnectionStatusProvider
from catchup.connector_core.ports.connection_status import ConnectionType

ConnectionStatusItemLoader = Callable[
    [ConnectionStatusProvider],
    list[ConnectionStatusItem],
]

CONNECTION_STATUS_VENDOR_LOADERS: dict[
    str,
    tuple[ConnectionType, ConnectionStatusItemLoader],
] = {
    "github": (
        ConnectionType.INSTALLATION,
        lambda provider: provider.list_github_installation_items(),
    ),
    "slack": (
        ConnectionType.OAUTH_TOKEN,
        lambda provider: provider.list_slack_oauth_token_items(),
    ),
    "atlassian": (
        ConnectionType.OAUTH_TOKEN,
        lambda provider: provider.list_atlassian_oauth_token_items(),
    ),
    "jira": (
        ConnectionType.OAUTH_TOKEN,
        lambda provider: provider.list_atlassian_oauth_token_items(),
    ),
    "confluence": (
        ConnectionType.OAUTH_TOKEN,
        lambda provider: provider.list_atlassian_oauth_token_items(),
    ),
    "channel-talk": (
        ConnectionType.CREDENTIAL,
        lambda provider: provider.list_channel_talk_credential_items(),
    ),
}


def normalize_vendor(vendor: str) -> str:
    return vendor.strip().lower().replace("_", "-")


def build_connection_status(
    *,
    vendor: str,
    connection_type: ConnectionType,
    items: list[ConnectionStatusItem],
) -> ConnectionStatus:
    return ConnectionStatus(
        vendor=vendor,
        connected=bool(items),
        connection_type=connection_type,
        count=len(items),
        items=items,
    )


class ConnectionStatusApplication:
    def __init__(
        self,
        *,
        provider: ConnectionStatusProvider,
    ) -> None:
        self.provider = provider

    def get_status(self, *, vendor: str) -> ConnectionStatus | None:
        normalized_vendor = normalize_vendor(vendor)
        status_loader = CONNECTION_STATUS_VENDOR_LOADERS.get(normalized_vendor)
        if status_loader is None:
            return None

        connection_type, load_items = status_loader
        return build_connection_status(
            vendor=normalized_vendor,
            connection_type=connection_type,
            items=load_items(self.provider),
        )
