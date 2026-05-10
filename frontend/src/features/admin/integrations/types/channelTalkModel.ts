// hydrate 시 보안상 평문 없는 키 필드를 채우는 마스킹 placeholder
export const MASKED_PLACEHOLDER = '●●●●●●●●';

export type ChannelTalkSyncInterval = '1hour' | '6hour' | '12hour' | '24hour';

// dropdown 옵션 + 선택값 표시 공용 라벨
export const CHANNEL_TALK_SYNC_INTERVAL_LABELS: Record<ChannelTalkSyncInterval, string> = {
  '1hour': '1시간',
  '6hour': '6시간',
  '12hour': '12시간',
  '24hour': '24시간',
};

// label union → 백엔드 polling_cycle_hours (int) 변환 매퍼
export const CHANNEL_TALK_SYNC_INTERVAL_HOURS: Record<ChannelTalkSyncInterval, number> = {
  '1hour': 1,
  '6hour': 6,
  '12hour': 12,
  '24hour': 24,
};

export const DOCUMENT_SPACE_SYNC_INTERVAL_OPTIONS: ChannelTalkSyncInterval[] = [
  '1hour',
  '6hour',
  '12hour',
  '24hour',
];
export const DOCUMENT_SPACE_SYNC_INTERVAL_DEFAULT: ChannelTalkSyncInterval = '1hour';

// idle: 입력 전 / tested: 검증 성공 collapsed lock / error: 검증 실패 expanded 유지
export type ChannelTalkConnectionStatus = 'idle' | 'tested' | 'error';

// 채널 하위 항목. 채널과 독립된 connectionStatus 보유
export interface ChannelTalkDocumentSpace {
  id: string;
  name: string;
  accessKey: string;
  accessSecret: string;
  syncInterval: ChannelTalkSyncInterval;
  connectionStatus: ChannelTalkConnectionStatus;
  errorMessage?: string;
}

export interface ChannelTalkChannel {
  id: string;
  name: string;
  accessKey: string;
  accessSecret: string;
  webhookToken: string;
  documentSpaces: ChannelTalkDocumentSpace[];
  connectionStatus: ChannelTalkConnectionStatus;
  errorMessage?: string;
}

export interface ChannelTalkConnectionState {
  connected: boolean;
  lastSyncedAt: string | null;
  channels: ChannelTalkChannel[];
}

// 외부에서 patch 가능한 필드만 — id/connectionStatus/errorMessage는 viewModel 전용 액션으로만 변경
export type ChannelTalkChannelPatch = Partial<
  Pick<ChannelTalkChannel, 'name' | 'accessKey' | 'accessSecret' | 'webhookToken' | 'documentSpaces'>
>;

export type ChannelTalkDocumentSpacePatch = Partial<
  Pick<ChannelTalkDocumentSpace, 'name' | 'accessKey' | 'accessSecret' | 'syncInterval'>
>;
