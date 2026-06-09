from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from datetime import datetime
from enum import StrEnum
from typing import Any
from typing import Iterator
from typing import Protocol

from pydantic import BaseModel
from pydantic import Field
from sqlalchemy.orm import Session

from catchup.db.atlassian import oauth_repository as atlassian_oauth_repository
from catchup.db.channel_talk.repository import ChannelTalkCredentialsRepository
from catchup.db.channel_talk.repository import ChannelTalkDocumentCredentialsRepository
from catchup.db.engine import SessionLocal
from catchup.db.github import installation_repository
from catchup.db.slack import oauth_repository as slack_oauth_repository

SessionFactory = Callable[[], Session]


class ConnectionType(StrEnum):
    OAUTH_TOKEN = "oauth_token"
    CREDENTIAL = "credential"
    INSTALLATION = "installation"


class ConnectionStatusItem(BaseModel):
    id: str
    name: str | None = None
    connected_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConnectionStatus(BaseModel):
    vendor: str
    connected: bool
    connection_type: ConnectionType
    count: int
    items: list[ConnectionStatusItem] = Field(default_factory=list)


class ConnectionStatusProvider(Protocol):
    def list_github_installation_items(self) -> list[ConnectionStatusItem]: ...

    def list_slack_oauth_token_items(self) -> list[ConnectionStatusItem]: ...

    def list_atlassian_oauth_token_items(self) -> list[ConnectionStatusItem]: ...

    def list_channel_talk_credential_items(self) -> list[ConnectionStatusItem]: ...


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
    "channel_talk": (
        ConnectionType.CREDENTIAL,
        lambda provider: provider.list_channel_talk_credential_items(),
    ),
}


def split_scopes(scopes: str | None) -> list[str]:
    if not scopes:
        return []
    return [scope for scope in scopes.split() if scope]


def normalize_vendor(vendor: str) -> str:
    return vendor.strip().lower()


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


class ConnectionStatusAdapter:
    """Integration API DB 조회 adapter."""

    def __init__(
        self,
        *,
        db: Session | None = None,
        session_factory: SessionFactory = SessionLocal,
    ) -> None:
        self.db = db
        self.session_factory = session_factory

    @contextmanager
    def _session(self) -> Iterator[Session]:
        if self.db is not None:
            yield self.db
            return

        with self.session_factory() as db:
            yield db

    def list_github_installation_items(self) -> list[ConnectionStatusItem]:
        with self._session() as db:
            installations = installation_repository.get_all_installations(db)
            return [
                ConnectionStatusItem(
                    id=str(installation.installation_id),
                    name=installation.account_login,
                    connected_at=installation.created_at,
                    metadata={
                        "account_type": installation.account_type,
                        "account_id": installation.account_id,
                        "repository_selection": installation.repository_selection,
                        "suspended_at": installation.suspended_at,
                    },
                )
                for installation in installations
            ]

    def list_slack_oauth_token_items(self) -> list[ConnectionStatusItem]:
        with self._session() as db:
            tokens = slack_oauth_repository.get_all_slack_tokens(db)
            return [
                ConnectionStatusItem(
                    id=token.team_id,
                    name=token.team_name,
                    connected_at=token.created_at,
                    metadata={
                        "bot_user_id": token.bot_user_id,
                        "scopes": split_scopes(token.bot_scopes),
                    },
                )
                for token in tokens
            ]

    def list_atlassian_oauth_token_items(self) -> list[ConnectionStatusItem]:
        with self._session() as db:
            tokens = atlassian_oauth_repository.get_all_tokens(db)
            return [
                ConnectionStatusItem(
                    id=token.cloud_id,
                    name=token.site_name,
                    connected_at=token.created_at,
                    metadata={
                        "atlassian_account_id": token.atlassian_account_id,
                        "site_url": token.site_url,
                        "scopes": split_scopes(token.scopes),
                    },
                )
                for token in tokens
            ]

    def list_channel_talk_credential_items(self) -> list[ConnectionStatusItem]:
        with self._session() as db:
            channel_connections = ChannelTalkCredentialsRepository(db).list_connections()
            document_connections = (
                ChannelTalkDocumentCredentialsRepository(db).list_document_connections()
            )

        items = [
            ConnectionStatusItem(
                id=connection.channel_id,
                name=connection.channel_name,
                connected_at=connection.credential_last_verified_at,
                metadata={
                    "credential_type": "channel",
                    "last_verified_at": connection.credential_last_verified_at,
                    "webhook_token_configured": bool(
                        str(connection.webhook_token or "").strip()
                    ),
                },
            )
            for connection in channel_connections
        ]
        items.extend(
            ConnectionStatusItem(
                id=connection.space_id,
                name=connection.space_name,
                connected_at=connection.credential_last_verified_at,
                metadata={
                    "credential_type": "document_space",
                    "channel_id": connection.channel_id,
                    "association_status": connection.association_status,
                    "last_verified_at": connection.credential_last_verified_at,
                    "polling_cycle_hours": connection.polling_cycle_hours,
                },
            )
            for connection in document_connections
        )
        return items
