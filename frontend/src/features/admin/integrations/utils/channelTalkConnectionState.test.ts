import { describe, expect, it } from 'vitest';

import type { ChannelTalkConnectResponse, ChannelTalkDocumentConnectResponse } from '../types/channelTalkApi';
import type { ChannelTalkChannel, ChannelTalkConnectionState, ChannelTalkDocumentSpace } from '../types/channelTalkModel';
import { MASKED_PLACEHOLDER } from '../types/channelTalkModel';
import {
  appendNewChannel,
  appendNewDocumentSpace,
  applyChannelPatch,
  applyChannelTestSuccess,
  applyDocumentSpacePatch,
  applyDocumentSpaceTestSuccess,
  markChannelError,
  removeChannelById,
  restoreChannelAt,
  restoreDocumentSpaceAt,
} from './channelTalkConnectionState';

const ds = (overrides: Partial<ChannelTalkDocumentSpace> = {}): ChannelTalkDocumentSpace => ({
  id: 'ds-1',
  name: '도큐먼트 스페이스 1',
  accessKey: 'dk',
  accessSecret: 'ds',
  syncInterval: '1hour',
  connectionStatus: 'idle',
  ...overrides,
});

const channel = (overrides: Partial<ChannelTalkChannel> = {}): ChannelTalkChannel => ({
  id: 'ch-1',
  name: '채널 1',
  accessKey: 'ak',
  accessSecret: 'as',
  webhookToken: 'wt',
  documentSpaces: [],
  connectionStatus: 'idle',
  ...overrides,
});

const state = (channels: ChannelTalkChannel[], overrides: Partial<ChannelTalkConnectionState> = {}): ChannelTalkConnectionState => ({
  connected: true,
  lastSyncedAt: null,
  channels,
  ...overrides,
});

describe('applyChannelPatch — 비밀키 변경 시 검증 리셋', () => {
  it('tested 채널의 비밀키가 바뀌면 idle로 돌아가고 에러 메시지가 비워진다', () => {
    const s = state([channel({ connectionStatus: 'tested', errorMessage: '이전 에러' })]);
    const next = applyChannelPatch(s, 'ch-1', { accessKey: 'changed' });
    expect(next.channels[0].connectionStatus).toBe('idle');
    expect(next.channels[0].errorMessage).toBeUndefined();
  });

  it('비밀키가 아닌 필드(name) 변경은 검증 상태를 유지한다', () => {
    const s = state([channel({ connectionStatus: 'tested' })]);
    const next = applyChannelPatch(s, 'ch-1', { name: '새 이름' });
    expect(next.channels[0].connectionStatus).toBe('tested');
  });

  it('비밀키 필드라도 같은 값이면 리셋하지 않는다', () => {
    const s = state([channel({ connectionStatus: 'tested', accessKey: 'ak' })]);
    const next = applyChannelPatch(s, 'ch-1', { accessKey: 'ak' });
    expect(next.channels[0].connectionStatus).toBe('tested');
  });

  it('다른 채널은 건드리지 않는다', () => {
    const s = state([channel(), channel({ id: 'ch-2', connectionStatus: 'tested' })]);
    const next = applyChannelPatch(s, 'ch-1', { accessKey: 'x' });
    expect(next.channels[1]).toBe(s.channels[1]);
  });
});

describe('applyDocumentSpacePatch', () => {
  it('도큐먼트 스페이스의 비밀키 변경도 같은 리셋 규칙을 따른다', () => {
    const s = state([channel({ documentSpaces: [ds({ connectionStatus: 'error', errorMessage: 'x' })] })]);
    const next = applyDocumentSpacePatch(s, 'ch-1', 'ds-1', { accessSecret: 'changed' });
    expect(next.channels[0].documentSpaces[0].connectionStatus).toBe('idle');
    expect(next.channels[0].documentSpaces[0].errorMessage).toBeUndefined();
  });

  it('syncInterval은 비밀키가 아니라 검증 상태를 유지한다', () => {
    const s = state([channel({ documentSpaces: [ds({ connectionStatus: 'tested' })] })]);
    const next = applyDocumentSpacePatch(s, 'ch-1', 'ds-1', { syncInterval: '24hour' });
    expect(next.channels[0].documentSpaces[0].connectionStatus).toBe('tested');
  });
});

describe('optimistic 삭제·복원', () => {
  it('마지막 채널을 지우면 connected가 내려간다', () => {
    const next = removeChannelById(state([channel()]), 'ch-1');
    expect(next.channels).toHaveLength(0);
    expect(next.connected).toBe(false);
  });

  it('채널이 남아 있으면 connected를 유지한다', () => {
    const next = removeChannelById(state([channel(), channel({ id: 'ch-2' })]), 'ch-1');
    expect(next.connected).toBe(true);
  });

  it('복원은 원래 인덱스에 들어가고, 인덱스가 길이를 넘으면 끝에 붙는다', () => {
    const a = channel({ id: 'a' });
    const b = channel({ id: 'b' });
    const restored = restoreChannelAt(state([b]), a, 0);
    expect(restored.channels.map((c) => c.id)).toEqual(['a', 'b']);

    const clamped = restoreChannelAt(state([b]), a, 5);
    expect(clamped.channels.map((c) => c.id)).toEqual(['b', 'a']);
  });

  it('도큐먼트 스페이스 복원도 해당 채널 안에서 인덱스를 지킨다', () => {
    const d1 = ds({ id: 'd1' });
    const d2 = ds({ id: 'd2' });
    const s = state([channel({ documentSpaces: [d2] })]);
    const next = restoreDocumentSpaceAt(s, 'ch-1', d1, 0);
    expect(next.channels[0].documentSpaces.map((d) => d.id)).toEqual(['d1', 'd2']);
  });
});

describe('연결 테스트 결과 반영', () => {
  const connectResponse = (overrides: Partial<ChannelTalkConnectResponse> = {}): ChannelTalkConnectResponse => ({
    installed: true,
    channel_id: 'backend-ch',
    channel_name: '백엔드 채널',
    credential_last_verified_at: '2026-08-04T00:00:00Z',
    webhook_token_configured: true,
    status_reason: null,
    status: 'connected',
    message: 'ok',
    ...overrides,
  });

  it('성공 시 백엔드 id/name으로 교체하고 키를 마스킹하며 connected를 올린다', () => {
    const s = state([channel()], { connected: false });
    const next = applyChannelTestSuccess(s, 'ch-1', connectResponse());
    const ch = next.channels[0];
    expect(ch.id).toBe('backend-ch');
    expect(ch.name).toBe('백엔드 채널');
    expect(ch.accessKey).toBe(MASKED_PLACEHOLDER);
    expect(ch.accessSecret).toBe(MASKED_PLACEHOLDER);
    expect(ch.webhookToken).toBe(MASKED_PLACEHOLDER);
    expect(ch.connectionStatus).toBe('tested');
    expect(next.connected).toBe(true);
    expect(next.lastSyncedAt).toBe('2026-08-04T00:00:00Z');
  });

  it('webhook 미설정 응답이면 webhookToken을 비운다', () => {
    const next = applyChannelTestSuccess(state([channel()]), 'ch-1', connectResponse({ webhook_token_configured: false }));
    expect(next.channels[0].webhookToken).toBe('');
  });

  it('백엔드가 id/name을 null로 주면 기존 값을 유지한다', () => {
    const next = applyChannelTestSuccess(
      state([channel()]),
      'ch-1',
      connectResponse({ channel_id: null, channel_name: null }),
    );
    expect(next.channels[0].id).toBe('ch-1');
    expect(next.channels[0].name).toBe('채널 1');
  });

  it('도큐먼트 스페이스 성공도 교체+마스킹 규칙이 같다', () => {
    const response: ChannelTalkDocumentConnectResponse = {
      installed: true,
      channel_id: 'backend-ch',
      space_id: 'backend-sp',
      space_name: '백엔드 스페이스',
      credential_last_verified_at: null,
      association_status: null,
      status_reason: null,
      status: 'connected',
      message: 'ok',
    };
    const s = state([channel({ documentSpaces: [ds()] })]);
    const next = applyDocumentSpaceTestSuccess(s, 'ch-1', 'ds-1', response);
    const space = next.channels[0].documentSpaces[0];
    expect(space.id).toBe('backend-sp');
    expect(space.accessKey).toBe(MASKED_PLACEHOLDER);
    expect(space.connectionStatus).toBe('tested');
  });

  it('markChannelError는 메시지 생략 시 기존 메시지를 비운다', () => {
    const s = state([channel({ errorMessage: '이전' })]);
    expect(markChannelError(s, 'ch-1').channels[0].errorMessage).toBeUndefined();
    expect(markChannelError(s, 'ch-1', '새 메시지').channels[0].errorMessage).toBe('새 메시지');
  });
});

describe('추가', () => {
  it('appendNewChannel은 순번 이름의 idle 채널을 뒤에 붙인다', () => {
    const next = appendNewChannel(state([channel()]));
    expect(next.channels).toHaveLength(2);
    expect(next.channels[1].name).toBe('채널 2');
    expect(next.channels[1].connectionStatus).toBe('idle');
  });

  it('appendNewDocumentSpace는 해당 채널에만 붙는다', () => {
    const s = state([channel(), channel({ id: 'ch-2' })]);
    const next = appendNewDocumentSpace(s, 'ch-2');
    expect(next.channels[0].documentSpaces).toHaveLength(0);
    expect(next.channels[1].documentSpaces).toHaveLength(1);
  });
});
