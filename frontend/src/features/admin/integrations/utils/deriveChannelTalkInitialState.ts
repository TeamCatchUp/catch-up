import type { ChannelTalkConnectionState } from '../types/channelTalkModel';
import { DOCUMENT_SPACE_SYNC_INTERVAL_DEFAULT, MASKED_PLACEHOLDER } from '../types/channelTalkModel';
import type { ChannelTalkConnectionStatusResponse } from '../types/connectionStatusApi';

// connection-status 응답 → viewModel 초기 state
// items는 channel/document_space 혼합 — credential_type으로 분기, channel_id로 자식 그룹화
// 키 필드는 보안상 응답에 없어 MASKED_PLACEHOLDER로 lock 시각화
export function deriveChannelTalkInitialState(
  response: ChannelTalkConnectionStatusResponse | undefined,
): ChannelTalkConnectionState {
  const items = response?.items ?? [];
  const channelItems = items.filter(
    (item): item is typeof item & { metadata: Extract<typeof item.metadata, { credential_type: 'channel' }> } =>
      item.metadata.credential_type === 'channel',
  );

  if (channelItems.length === 0) {
    return { connected: false, lastSyncedAt: null, channels: [] };
  }

  const spaceItems = items.filter(
    (item): item is typeof item & {
      metadata: Extract<typeof item.metadata, { credential_type: 'document_space' }>;
    } => item.metadata.credential_type === 'document_space',
  );

  const channels = channelItems.map((channelItem) => ({
    id: channelItem.id,
    name: channelItem.name ?? '',
    accessKey: MASKED_PLACEHOLDER,
    accessSecret: MASKED_PLACEHOLDER,
    webhookToken: channelItem.metadata.webhook_token_configured ? MASKED_PLACEHOLDER : '',
    documentSpaces: spaceItems
      .filter((space) => space.metadata.channel_id === channelItem.id)
      .map((space) => ({
        id: space.id,
        name: space.name ?? '',
        accessKey: MASKED_PLACEHOLDER,
        accessSecret: MASKED_PLACEHOLDER,
        syncInterval: DOCUMENT_SPACE_SYNC_INTERVAL_DEFAULT,
        connectionStatus: 'tested' as const,
      })),
    connectionStatus: 'tested' as const,
  }));

  const verifiedTimes = channelItems
    .map((item) => item.metadata.last_verified_at)
    .filter((t): t is string => !!t);
  const lastSyncedAt = verifiedTimes.length > 0 ? [...verifiedTimes].sort().at(-1) ?? null : null;

  return {
    connected: true,
    lastSyncedAt,
    channels,
  };
}
