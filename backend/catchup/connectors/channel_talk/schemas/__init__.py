from __future__ import annotations

from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkConnectRequest as ChannelTalkConnectRequest,
)
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkCredentialsRecord as ChannelTalkCredentialsRecord,
)
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkCredentialsStatus as ChannelTalkCredentialsStatus,
)
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkCredentialsUpsert as ChannelTalkCredentialsUpsert,
)
from catchup.connectors.channel_talk.schemas.channel_connection import (
    ChannelTalkUninstallResult as ChannelTalkUninstallResult,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkChannel as ChannelTalkChannel,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkChannelMetadata as ChannelTalkChannelMetadata,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkCurrentChannel as ChannelTalkCurrentChannel,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkGroupManagerMembership as ChannelTalkGroupManagerMembership,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkGroupMetadata as ChannelTalkGroupMetadata,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkGroupMetadataPage as ChannelTalkGroupMetadataPage,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkManager as ChannelTalkManager,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkManagerMetadata as ChannelTalkManagerMetadata,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkManagerMetadataPage as ChannelTalkManagerMetadataPage,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkMetadataSyncRequest as ChannelTalkMetadataSyncRequest,
)
from catchup.connectors.channel_talk.schemas.channel_metadata import (
    ChannelTalkMetadataSyncResult as ChannelTalkMetadataSyncResult,
)
from catchup.connectors.channel_talk.schemas.document_article import (
    ChannelTalkDocumentArticle as ChannelTalkDocumentArticle,
)
from catchup.connectors.channel_talk.schemas.document_article import (
    ChannelTalkDocumentArticleBatch as ChannelTalkDocumentArticleBatch,
)
from catchup.connectors.channel_talk.schemas.document_article import (
    ChannelTalkDocumentArticleBatchResult as ChannelTalkDocumentArticleBatchResult,
)
from catchup.connectors.channel_talk.schemas.document_article import (
    ChannelTalkDocumentArticleCategory as ChannelTalkDocumentArticleCategory,
)
from catchup.connectors.channel_talk.schemas.document_article import (
    ChannelTalkDocumentArticleDetail as ChannelTalkDocumentArticleDetail,
)
from catchup.connectors.channel_talk.schemas.document_article import (
    ChannelTalkDocumentArticlePage as ChannelTalkDocumentArticlePage,
)
from catchup.connectors.channel_talk.schemas.document_article import (
    ChannelTalkDocumentArticleState as ChannelTalkDocumentArticleState,
)
from catchup.connectors.channel_talk.schemas.document_article import (
    ChannelTalkDocumentArticleView as ChannelTalkDocumentArticleView,
)
from catchup.connectors.channel_talk.schemas.document_article import (
    ChannelTalkDocumentTopic as ChannelTalkDocumentTopic,
)
from catchup.connectors.channel_talk.schemas.document_article import (
    ChannelTalkDocumentWebsite as ChannelTalkDocumentWebsite,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentAssociationStatus as ChannelTalkDocumentAssociationStatus,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentConnectRequest as ChannelTalkDocumentConnectRequest,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentCredentialsRecord as ChannelTalkDocumentCredentialsRecord,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentCredentialsStatus as ChannelTalkDocumentCredentialsStatus,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentCredentialsUpsert as ChannelTalkDocumentCredentialsUpsert,
)
from catchup.connectors.channel_talk.schemas.document_connection import (
    ChannelTalkDocumentUninstallResult as ChannelTalkDocumentUninstallResult,
)
from catchup.connectors.channel_talk.schemas.document_metadata import (
    ChannelTalkDocumentAuthorMetadata as ChannelTalkDocumentAuthorMetadata,
)
from catchup.connectors.channel_talk.schemas.document_metadata import (
    ChannelTalkDocumentAuthorPage as ChannelTalkDocumentAuthorPage,
)
from catchup.connectors.channel_talk.schemas.document_metadata import (
    ChannelTalkDocumentMetadataSyncRequest as ChannelTalkDocumentMetadataSyncRequest,
)
from catchup.connectors.channel_talk.schemas.document_metadata import (
    ChannelTalkDocumentMetadataSyncResult as ChannelTalkDocumentMetadataSyncResult,
)
from catchup.connectors.channel_talk.schemas.document_metadata import (
    ChannelTalkDocumentNavNodeMetadata as ChannelTalkDocumentNavNodeMetadata,
)
from catchup.connectors.channel_talk.schemas.document_metadata import (
    ChannelTalkDocumentNavNodePage as ChannelTalkDocumentNavNodePage,
)
from catchup.connectors.channel_talk.schemas.document_metadata import (
    ChannelTalkDocumentSpace as ChannelTalkDocumentSpace,
)
from catchup.connectors.channel_talk.schemas.user import (
    ChannelTalkUserFoundation as ChannelTalkUserFoundation,
)
from catchup.connectors.channel_talk.schemas.user_chat import (
    ChannelTalkUserChatAnchors as ChannelTalkUserChatAnchors,
)
from catchup.connectors.channel_talk.schemas.user_chat import (
    ChannelTalkUserChatAssignment as ChannelTalkUserChatAssignment,
)
from catchup.connectors.channel_talk.schemas.user_chat import (
    ChannelTalkUserChatDetail as ChannelTalkUserChatDetail,
)
from catchup.connectors.channel_talk.schemas.user_chat import (
    ChannelTalkUserChatListItem as ChannelTalkUserChatListItem,
)
from catchup.connectors.channel_talk.schemas.user_chat import (
    ChannelTalkUserChatListPage as ChannelTalkUserChatListPage,
)
from catchup.connectors.channel_talk.schemas.user_chat import (
    ChannelTalkUserChatManagerRef as ChannelTalkUserChatManagerRef,
)
from catchup.connectors.channel_talk.schemas.user_chat import (
    ChannelTalkUserChatMetrics as ChannelTalkUserChatMetrics,
)
from catchup.connectors.channel_talk.schemas.user_chat import (
    ChannelTalkUserChatState as ChannelTalkUserChatState,
)
from catchup.connectors.channel_talk.schemas.user_chat import (
    ChannelTalkUserChatTag as ChannelTalkUserChatTag,
)
from catchup.connectors.channel_talk.schemas.user_chat import (
    ChannelTalkUserChatTiming as ChannelTalkUserChatTiming,
)
from catchup.connectors.channel_talk.schemas.user_chat import (
    FullSyncQuotaSnapshot as FullSyncQuotaSnapshot,
)
from catchup.connectors.channel_talk.schemas.user_chat_message import (
    ChannelTalkUserChatMessage as ChannelTalkUserChatMessage,
)
from catchup.connectors.channel_talk.schemas.user_chat_message import (
    ChannelTalkUserChatMessageAttachment as ChannelTalkUserChatMessageAttachment,
)
from catchup.connectors.channel_talk.schemas.user_chat_message import (
    ChannelTalkUserChatMessageAuthor as ChannelTalkUserChatMessageAuthor,
)
from catchup.connectors.channel_talk.schemas.user_chat_message import (
    ChannelTalkUserChatMessageBlock as ChannelTalkUserChatMessageBlock,
)
from catchup.connectors.channel_talk.schemas.user_chat_message import (
    ChannelTalkUserChatMessageButton as ChannelTalkUserChatMessageButton,
)
from catchup.connectors.channel_talk.schemas.user_chat_message import (
    ChannelTalkUserChatMessageForm as ChannelTalkUserChatMessageForm,
)
from catchup.connectors.channel_talk.schemas.user_chat_message import (
    ChannelTalkUserChatMessageFormInput as ChannelTalkUserChatMessageFormInput,
)
from catchup.connectors.channel_talk.schemas.user_chat_message import (
    ChannelTalkUserChatMessageLog as ChannelTalkUserChatMessageLog,
)
from catchup.connectors.channel_talk.schemas.user_chat_message import (
    ChannelTalkUserChatMessagePage as ChannelTalkUserChatMessagePage,
)
from catchup.connectors.channel_talk.schemas.user_chat_message import (
    ChannelTalkUserChatMessageWebPage as ChannelTalkUserChatMessageWebPage,
)

__all__ = (
    "ChannelTalkChannel",
    "ChannelTalkChannelMetadata",
    "ChannelTalkConnectRequest",
    "ChannelTalkCredentialsRecord",
    "ChannelTalkCredentialsStatus",
    "ChannelTalkCredentialsUpsert",
    "ChannelTalkCurrentChannel",
    "ChannelTalkDocumentArticle",
    "ChannelTalkDocumentArticleBatch",
    "ChannelTalkDocumentArticleBatchResult",
    "ChannelTalkDocumentArticleCategory",
    "ChannelTalkDocumentArticleDetail",
    "ChannelTalkDocumentArticlePage",
    "ChannelTalkDocumentArticleState",
    "ChannelTalkDocumentArticleView",
    "ChannelTalkDocumentAssociationStatus",
    "ChannelTalkDocumentAuthorMetadata",
    "ChannelTalkDocumentAuthorPage",
    "ChannelTalkDocumentConnectRequest",
    "ChannelTalkDocumentCredentialsRecord",
    "ChannelTalkDocumentCredentialsStatus",
    "ChannelTalkDocumentCredentialsUpsert",
    "ChannelTalkDocumentMetadataSyncRequest",
    "ChannelTalkDocumentMetadataSyncResult",
    "ChannelTalkDocumentNavNodeMetadata",
    "ChannelTalkDocumentNavNodePage",
    "ChannelTalkDocumentSpace",
    "ChannelTalkDocumentTopic",
    "ChannelTalkDocumentUninstallResult",
    "ChannelTalkDocumentWebsite",
    "ChannelTalkGroupManagerMembership",
    "ChannelTalkGroupMetadata",
    "ChannelTalkGroupMetadataPage",
    "ChannelTalkManager",
    "ChannelTalkManagerMetadata",
    "ChannelTalkManagerMetadataPage",
    "ChannelTalkMetadataSyncRequest",
    "ChannelTalkMetadataSyncResult",
    "ChannelTalkUninstallResult",
    "ChannelTalkUserChatAnchors",
    "ChannelTalkUserChatAssignment",
    "ChannelTalkUserChatDetail",
    "ChannelTalkUserChatListItem",
    "ChannelTalkUserChatListPage",
    "ChannelTalkUserChatManagerRef",
    "ChannelTalkUserChatMessage",
    "ChannelTalkUserChatMessageAttachment",
    "ChannelTalkUserChatMessageAuthor",
    "ChannelTalkUserChatMessageBlock",
    "ChannelTalkUserChatMessageButton",
    "ChannelTalkUserChatMessageForm",
    "ChannelTalkUserChatMessageFormInput",
    "ChannelTalkUserChatMessageLog",
    "ChannelTalkUserChatMessagePage",
    "ChannelTalkUserChatMessageWebPage",
    "ChannelTalkUserChatMetrics",
    "ChannelTalkUserChatState",
    "ChannelTalkUserChatTag",
    "ChannelTalkUserChatTiming",
    "ChannelTalkUserFoundation",
    "FullSyncQuotaSnapshot",
)
