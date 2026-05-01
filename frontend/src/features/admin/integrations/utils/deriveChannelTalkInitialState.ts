import type {
  ChannelTalkDocumentStatusResponse,
  ChannelTalkStatusResponse,
} from '../types/channelTalkApi';
import type { ChannelTalkConnectionState } from '../types/channelTalkModel';
import {
  CHANNEL_SYNC_INTERVAL_DEFAULT,
  DOCUMENT_SPACE_SYNC_INTERVAL_DEFAULT,
  MASKED_PLACEHOLDER,
} from '../types/channelTalkModel';

/**
 * 백엔드 GET 응답(list)으로부터 viewModel 초기 state를 derive.
 *
 * - 등록된 channel N개를 카드 N개로 매핑
 * - 각 channel에 속한 document space들을 그 카드의 자식으로 그룹화 (channel_id 기준)
 * - 키 필드는 보안상 응답에 없으므로 MASKED_PLACEHOLDER로 채워서 lock 상태 시각화
 * - lastSyncedAt은 모든 channel 중 가장 최근 검증 시각으로 노출 (ISO 사전순 = 시간순)
 *
 * 호출처: `ChannelTalkManagementPanel`이 mount 시 1회만 실행 후 `useChannelTalkViewModel`의
 * `initialState` prop으로 전달. mount/unmount 패턴으로 React 19 set-state-in-effect 룰 회피.
 */
export function deriveChannelTalkInitialState(
  channelDataList: ChannelTalkStatusResponse[] | undefined,
  documentDataList: ChannelTalkDocumentStatusResponse[] | undefined,
): ChannelTalkConnectionState {
  const installedChannels = (channelDataList ?? []).filter(
    (c): c is ChannelTalkStatusResponse & { channel_id: string } => c.installed && !!c.channel_id,
  );

  if (installedChannels.length === 0) {
    return { connected: false, lastSyncedAt: null, channels: [] };
  }

  const installedDocuments = (documentDataList ?? []).filter(
    (d): d is ChannelTalkDocumentStatusResponse & { channel_id: string; space_id: string } =>
      d.installed && !!d.channel_id && !!d.space_id,
  );

  const channels = installedChannels.map((channelData) => ({
    id: channelData.channel_id,
    name: channelData.channel_name ?? '',
    accessKey: MASKED_PLACEHOLDER,
    accessSecret: MASKED_PLACEHOLDER,
    webhookToken: channelData.webhook_token_configured ? MASKED_PLACEHOLDER : '',
    syncInterval: CHANNEL_SYNC_INTERVAL_DEFAULT,
    documentSpaces: installedDocuments
      .filter((d) => d.channel_id === channelData.channel_id)
      .map((d) => ({
        id: d.space_id,
        name: d.space_name ?? '',
        accessKey: MASKED_PLACEHOLDER,
        accessSecret: MASKED_PLACEHOLDER,
        syncInterval: DOCUMENT_SPACE_SYNC_INTERVAL_DEFAULT,
        connectionStatus: 'tested' as const,
      })),
    connectionStatus: 'tested' as const,
  }));

  const verifiedTimes = installedChannels
    .map((c) => c.credential_last_verified_at)
    .filter((t): t is string => !!t);
  const lastSyncedAt = verifiedTimes.length > 0 ? [...verifiedTimes].sort().at(-1) ?? null : null;

  return {
    connected: true,
    lastSyncedAt,
    channels,
  };
}
