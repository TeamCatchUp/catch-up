/** 채널톡 동기화 주기 옵션 (channel + documentSpace 공용 union) */
export type ChannelTalkSyncInterval = '5min' | '15min' | '30min' | '1hour' | '6hour' | '12hour' | '24hour';

/** 동기화 주기 표시 라벨 (dropdown 옵션 + 선택값 표시 공용) */
export const CHANNEL_TALK_SYNC_INTERVAL_LABELS: Record<ChannelTalkSyncInterval, string> = {
  '5min': '5분',
  '15min': '15분',
  '30min': '30분',
  '1hour': '1시간',
  '6hour': '6시간',
  '12hour': '12시간',
  '24hour': '24시간',
};

/**
 * 채널 카드 동기화 주기 옵션 — 실시간 대화 채널이라 짧은 주기 4개.
 * 5분이 기본값.
 */
export const CHANNEL_SYNC_INTERVAL_OPTIONS: ChannelTalkSyncInterval[] = ['5min', '15min', '30min', '1hour'];
export const CHANNEL_SYNC_INTERVAL_DEFAULT: ChannelTalkSyncInterval = '5min';

/**
 * 도큐먼트 스페이스 동기화 주기 옵션 — 정적 문서라 긴 주기 4개.
 * 1시간이 기본값.
 */
export const DOCUMENT_SPACE_SYNC_INTERVAL_OPTIONS: ChannelTalkSyncInterval[] = [
  '1hour',
  '6hour',
  '12hour',
  '24hour',
];
export const DOCUMENT_SPACE_SYNC_INTERVAL_DEFAULT: ChannelTalkSyncInterval = '1hour';

/**
 * 채널 카드 연결 상태 머신.
 * - `idle`: 입력 전 — 빈 placeholder
 * - `entered`: 입력 완료, 미검증
 * - `tested`: 연결 테스트 성공
 * - `error`: 검증 실패 (필드 1.5px destructive border + eye 토글 + 에러 메시지)
 * - `editing`: Key 수정 중 (focus border + cursor + "연결 테스트하기" 버튼 active)
 */
export type ChannelTalkConnectionStatus = 'idle' | 'entered' | 'tested' | 'error' | 'editing';

/** 채널톡 도큐먼트 스페이스 (채널 하위 항목) */
export interface ChannelTalkDocumentSpace {
  id: string;
  name: string;
  accessKey: string;
  accessSecret: string;
  syncInterval: ChannelTalkSyncInterval;
}

/** 채널톡 채널 — Access Key/Secret/Webhook + 동기화 주기 + 하위 도큐먼트 스페이스 + 검증 상태 */
export interface ChannelTalkChannel {
  id: string;
  name: string;
  accessKey: string;
  accessSecret: string;
  webhookToken: string;
  syncInterval: ChannelTalkSyncInterval;
  documentSpaces: ChannelTalkDocumentSpace[];
  connectionStatus: ChannelTalkConnectionStatus;
  /** error 상태일 때 표시할 에러 메시지 (없으면 빈 문자열) */
  errorMessage?: string;
}

/** 채널톡 연동 전체 상태 (mock 표시용) */
export interface ChannelTalkConnectionState {
  connected: boolean;
  /** 표시용 포맷된 시각 (예: "2026. 2. 9. 01:31") — 실제 API 도입 시 ISO 문자열로 교체 */
  lastSyncedAt: string | null;
  channels: ChannelTalkChannel[];
}
