import type { ChannelTalkConnectResponse, ChannelTalkDocumentConnectResponse } from '../types/channelTalkApi';
import type {
  ChannelTalkChannel,
  ChannelTalkChannelPatch,
  ChannelTalkConnectionState,
  ChannelTalkDocumentSpace,
  ChannelTalkDocumentSpacePatch,
} from '../types/channelTalkModel';
import { DOCUMENT_SPACE_SYNC_INTERVAL_DEFAULT, MASKED_PLACEHOLDER } from '../types/channelTalkModel';

/**
 * 채널톡 연동 화면 상태의 순수 전이 함수들.
 * `useChannelTalkViewModel`에서 추출했다 — 훅은 mutation·토스트·pending 추적만 갖고,
 * 상태가 어떻게 변하는가는 전부 여기서 정한다(renderHook 없이 테스트 가능).
 *
 * 채널과 도큐먼트 스페이스는 같은 규칙(비밀키 변경 시 검증 리셋, optimistic 삭제·복원,
 * 검증 성공 시 백엔드 id로 교체 + 키 마스킹)을 공유하므로 내부 map 헬퍼로 중복을 없앤다.
 */

// 미검증 카드의 임시 client-side ID. 검증 통과 시 백엔드 channel_id/space_id로 교체
export function makeLocalId(prefix: string): string {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

const mapChannel = (
  state: ChannelTalkConnectionState,
  channelId: string,
  fn: (channel: ChannelTalkChannel) => ChannelTalkChannel,
): ChannelTalkConnectionState => ({
  ...state,
  channels: state.channels.map((ch) => (ch.id === channelId ? fn(ch) : ch)),
});

const mapDocumentSpace = (
  state: ChannelTalkConnectionState,
  channelId: string,
  dsId: string,
  fn: (ds: ChannelTalkDocumentSpace) => ChannelTalkDocumentSpace,
): ChannelTalkConnectionState =>
  mapChannel(state, channelId, (ch) => ({
    ...ch,
    documentSpaces: ch.documentSpaces.map((ds) => (ds.id === dsId ? fn(ds) : ds)),
  }));

// ─── 추가 ───

export function appendNewChannel(state: ChannelTalkConnectionState): ChannelTalkConnectionState {
  return {
    ...state,
    channels: [
      ...state.channels,
      {
        id: makeLocalId('ch'),
        name: `채널 ${state.channels.length + 1}`,
        accessKey: '',
        accessSecret: '',
        webhookToken: '',
        documentSpaces: [],
        connectionStatus: 'idle',
      },
    ],
  };
}

export function appendNewDocumentSpace(
  state: ChannelTalkConnectionState,
  channelId: string,
): ChannelTalkConnectionState {
  return mapChannel(state, channelId, (ch) => ({
    ...ch,
    documentSpaces: [
      ...ch.documentSpaces,
      {
        id: makeLocalId('ds'),
        name: `도큐먼트 스페이스 ${ch.documentSpaces.length + 1}`,
        accessKey: '',
        accessSecret: '',
        syncInterval: DOCUMENT_SPACE_SYNC_INTERVAL_DEFAULT,
        connectionStatus: 'idle',
      },
    ],
  }));
}

// ─── 편집 (비밀키 변경 시 기존 검증 결과 무효화) ───

/** patch에 비밀 필드가 있고 값이 실제로 달라졌는가 */
const secretsChanged = <T extends object>(current: T, patch: Partial<T>, secretKeys: readonly (keyof T)[]): boolean =>
  secretKeys.some((key) => key in patch && patch[key] !== current[key]);

const CHANNEL_SECRET_KEYS = ['accessKey', 'accessSecret', 'webhookToken'] as const;
const DOCUMENT_SECRET_KEYS = ['accessKey', 'accessSecret'] as const;

const withValidationReset = <T extends { connectionStatus: ChannelTalkChannel['connectionStatus']; errorMessage?: string }>(
  current: T,
  next: T,
  changed: boolean,
): T => {
  const hadValidation = current.connectionStatus === 'tested' || current.connectionStatus === 'error';
  if (hadValidation && changed) return { ...next, connectionStatus: 'idle', errorMessage: undefined };
  return next;
};

export function applyChannelPatch(
  state: ChannelTalkConnectionState,
  channelId: string,
  patch: ChannelTalkChannelPatch,
): ChannelTalkConnectionState {
  return mapChannel(state, channelId, (ch) =>
    withValidationReset(ch, { ...ch, ...patch }, secretsChanged(ch, patch, CHANNEL_SECRET_KEYS)),
  );
}

export function applyDocumentSpacePatch(
  state: ChannelTalkConnectionState,
  channelId: string,
  dsId: string,
  patch: ChannelTalkDocumentSpacePatch,
): ChannelTalkConnectionState {
  return mapDocumentSpace(state, channelId, dsId, (ds) =>
    withValidationReset(ds, { ...ds, ...patch }, secretsChanged(ds, patch, DOCUMENT_SECRET_KEYS)),
  );
}

// ─── optimistic 삭제·복원 ───

/** 마지막 채널을 지우면 connected도 내린다 */
export function removeChannelById(state: ChannelTalkConnectionState, channelId: string): ChannelTalkConnectionState {
  const nextChannels = state.channels.filter((ch) => ch.id !== channelId);
  return { ...state, channels: nextChannels, connected: nextChannels.length > 0 && state.connected };
}

/** 백엔드 삭제 실패 시 원래 인덱스에 복원 (인덱스는 현재 길이로 클램프) */
export function restoreChannelAt(
  state: ChannelTalkConnectionState,
  channel: ChannelTalkChannel,
  index: number,
): ChannelTalkConnectionState {
  const next = [...state.channels];
  next.splice(Math.min(index, next.length), 0, channel);
  return { ...state, channels: next };
}

export function removeDocumentSpaceById(
  state: ChannelTalkConnectionState,
  channelId: string,
  dsId: string,
): ChannelTalkConnectionState {
  return mapChannel(state, channelId, (ch) => ({
    ...ch,
    documentSpaces: ch.documentSpaces.filter((ds) => ds.id !== dsId),
  }));
}

export function restoreDocumentSpaceAt(
  state: ChannelTalkConnectionState,
  channelId: string,
  ds: ChannelTalkDocumentSpace,
  index: number,
): ChannelTalkConnectionState {
  return mapChannel(state, channelId, (ch) => {
    const next = [...ch.documentSpaces];
    next.splice(Math.min(index, next.length), 0, ds);
    return { ...ch, documentSpaces: next };
  });
}

// ─── 연결 테스트 결과 반영 ───

/** errorMessage를 생략하면 비운다 — raw 영문 에러가 inline에 노출되지 않게 하는 기존 규칙 */
export function markChannelError(
  state: ChannelTalkConnectionState,
  channelId: string,
  errorMessage?: string,
): ChannelTalkConnectionState {
  return mapChannel(state, channelId, (ch) => ({ ...ch, connectionStatus: 'error', errorMessage }));
}

export function markDocumentSpaceError(
  state: ChannelTalkConnectionState,
  channelId: string,
  dsId: string,
  errorMessage?: string,
): ChannelTalkConnectionState {
  return mapDocumentSpace(state, channelId, dsId, (ds) => ({ ...ds, connectionStatus: 'error', errorMessage }));
}

/** 검증 성공 — 백엔드 발급 id/name으로 교체, 키 마스킹, connected 동기화 */
export function applyChannelTestSuccess(
  state: ChannelTalkConnectionState,
  channelId: string,
  data: ChannelTalkConnectResponse,
): ChannelTalkConnectionState {
  const next = mapChannel(state, channelId, (ch) => ({
    ...ch,
    id: data.channel_id ?? ch.id,
    name: data.channel_name ?? ch.name,
    accessKey: MASKED_PLACEHOLDER,
    accessSecret: MASKED_PLACEHOLDER,
    webhookToken: data.webhook_token_configured ? MASKED_PLACEHOLDER : '',
    connectionStatus: 'tested' as const,
    errorMessage: undefined,
  }));
  return { ...next, connected: true, lastSyncedAt: data.credential_last_verified_at };
}

export function applyDocumentSpaceTestSuccess(
  state: ChannelTalkConnectionState,
  channelId: string,
  dsId: string,
  data: ChannelTalkDocumentConnectResponse,
): ChannelTalkConnectionState {
  return mapDocumentSpace(state, channelId, dsId, (ds) => ({
    ...ds,
    id: data.space_id ?? ds.id,
    name: data.space_name ?? ds.name,
    accessKey: MASKED_PLACEHOLDER,
    accessSecret: MASKED_PLACEHOLDER,
    connectionStatus: 'tested' as const,
    errorMessage: undefined,
  }));
}
