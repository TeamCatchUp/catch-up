"""Channel Talk connector client/service/contracts."""

from catchup.connectors.channel_talk.core.client import ChannelTalkCoreApiClient
from catchup.connectors.channel_talk.exceptions import ChannelTalkAuthenticationError
from catchup.connectors.channel_talk.exceptions import ChannelTalkConflictError
from catchup.connectors.channel_talk.exceptions import ChannelTalkError
from catchup.connectors.channel_talk.exceptions import ChannelTalkPayloadError
from catchup.connectors.channel_talk.exceptions import ChannelTalkPersistenceError
from catchup.connectors.channel_talk.exceptions import ChannelTalkRateLimitError
from catchup.connectors.channel_talk.exceptions import ChannelTalkTimeoutError
from catchup.connectors.channel_talk.exceptions import ChannelTalkUpstreamError
from catchup.connectors.channel_talk.exceptions import ChannelTalkValidationError
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkConnectRequest,
)
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkCredentialsRecord,
)
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkCredentialsStatus,
)
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkCredentialsUpsert,
)
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkUninstallResult,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import ChannelTalkChannel
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkChannelMetadata,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkCurrentChannel,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkGroupManagerMembership,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkGroupMetadata,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import ChannelTalkManager
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkManagerMetadata,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkMetadataSyncRequest,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkMetadataSyncResult,
)
from catchup.connectors.channel_talk.schemas.user import ChannelTalkUserFoundation
from catchup.connectors.channel_talk.schemas.user_chat import ChannelTalkUserChatDetail
from catchup.connectors.channel_talk.schemas.user_chat import (
    ChannelTalkUserChatListItem,
)
from catchup.connectors.channel_talk.schemas.user_chat import (
    ChannelTalkUserChatListPage,
)
from catchup.connectors.channel_talk.schemas.user_chat import ChannelTalkUserChatState
from catchup.connectors.channel_talk.schemas.user_chat import FullSyncQuotaSnapshot
from catchup.connectors.channel_talk.schemas.user_chat_message import (
    ChannelTalkUserChatMessage,
)
from catchup.connectors.channel_talk.schemas.user_chat_message import (
    ChannelTalkUserChatMessagePage,
)

__all__ = [
    "ChannelTalkCoreApiClient",
    "ChannelTalkAuthenticationError",
    "ChannelTalkChannel",
    "ChannelTalkChannelMetadata",
    "ChannelTalkConflictError",
    "ChannelTalkConnectRequest",
    "ChannelTalkCredentialsRecord",
    "ChannelTalkCredentialsStatus",
    "ChannelTalkCredentialsUpsert",
    "ChannelTalkCurrentChannel",
    "ChannelTalkError",
    "ChannelTalkGroupManagerMembership",
    "ChannelTalkGroupMetadata",
    "ChannelTalkManager",
    "ChannelTalkManagerMetadata",
    "ChannelTalkMetadataSyncRequest",
    "ChannelTalkMetadataSyncResult",
    "ChannelTalkPayloadError",
    "ChannelTalkPersistenceError",
    "ChannelTalkRateLimitError",
    "ChannelTalkTimeoutError",
    "FullSyncQuotaSnapshot",
    "ChannelTalkUserChatDetail",
    "ChannelTalkUserChatListItem",
    "ChannelTalkUserChatListPage",
    "ChannelTalkUserChatMessage",
    "ChannelTalkUserChatMessagePage",
    "ChannelTalkUserChatState",
    "ChannelTalkUninstallResult",
    "ChannelTalkUpstreamError",
    "ChannelTalkUserFoundation",
    "ChannelTalkValidationError",
]
