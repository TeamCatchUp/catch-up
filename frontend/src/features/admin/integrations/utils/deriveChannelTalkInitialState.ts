import type { ChannelTalkConnectionState } from '../types/channelTalkModel';
import { MASKED_PLACEHOLDER, syncIntervalFromHours } from '../types/channelTalkModel';
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
    return { connected: false, credentialVerifiedAt: null, channels: [] };
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
        // 서버 저장값으로 hydrate — 기본값으로 채우면 재제출 때 서버 주기를 덮어쓴다
        syncInterval: syncIntervalFromHours(space.metadata.polling_cycle_hours),
        connectionStatus: 'tested' as const,
      })),
    connectionStatus: 'tested' as const,
  }));

  const verifiedTimes = channelItems
    .map((item) => item.metadata.last_verified_at)
    .filter((t): t is string => !!t);
  const credentialVerifiedAt = verifiedTimes.length > 0 ? [...verifiedTimes].sort().at(-1) ?? null : null;

  return {
    connected: true,
    credentialVerifiedAt,
    channels,
  };
}
