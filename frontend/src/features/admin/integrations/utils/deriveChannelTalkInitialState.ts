import type { ChannelTalkConnectionState } from '../types/channelTalkModel';
import { DOCUMENT_SPACE_SYNC_INTERVAL_DEFAULT, MASKED_PLACEHOLDER } from '../types/channelTalkModel';
import type { ChannelTalkConnectionStatusResponse } from '../types/connectionStatusApi';

/**
 * canonical connection-status(channel_talk) 응답으로부터 viewModel 초기 state를 derive.
 *
 * - items[]는 channel/document_space가 섞여 옴 — `metadata.credential_type`으로 분기
 * - 등록된 channel N개를 카드 N개로 매핑
 * - 각 channel에 속한 document space들을 그 카드의 자식으로 그룹화 (metadata.channel_id 기준)
 * - 키 필드는 보안상 응답에 없으므로 MASKED_PLACEHOLDER로 채워서 lock 상태 시각화
 * - lastSyncedAt은 모든 channel 중 가장 최근 검증 시각으로 노출 (ISO 사전순 = 시간순)
 *
 * 호출처: `ChannelTalkManagementPanel`이 mount 시 1회만 실행 후 `useChannelTalkViewModel`의
 * `initialState` prop으로 전달. mount/unmount 패턴으로 React 19 set-state-in-effect 룰 회피.
 */
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
