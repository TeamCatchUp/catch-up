import { describe, expect, it } from 'vitest';

import type { Period } from '../constants/period';
import { groupChannelTalkSyncDispatch, pickSyncDays } from './channelTalkSyncDispatch';
import type { ChannelTalkChannel } from './mapChannelTalkSyncTargets';

const channelA: ChannelTalkChannel = {
  channel_id: 'ch-a',
  display_name: 'Channel A',
  document_spaces: [
    { space_id: 'sp-1', display_name: 'Space 1' },
    { space_id: 'sp-2', display_name: 'Space 2' },
  ],
};

const channelB: ChannelTalkChannel = {
  channel_id: 'ch-b',
  display_name: 'Channel B',
  document_spaces: [{ space_id: 'sp-3', display_name: 'Space 3' }],
};

describe('groupChannelTalkSyncDispatch', () => {
  it('아무것도 선택 안 되면 빈 배열', () => {
    const result = groupChannelTalkSyncDispatch([channelA], new Set(), new Set(), {}, {});
    expect(result).toEqual([]);
  });

  it('채널만 선택 (스페이스 미선택) — channel target 1개, 채널 period 수집', () => {
    const result = groupChannelTalkSyncDispatch(
      [channelA],
      new Set(['ch-a']),
      new Set(),
      { 'ch-a': '3개월' },
      {},
    );
    expect(result).toHaveLength(1);
    expect(result[0].targets).toEqual([{ target_type: 'channel', target_id: 'ch-a' }]);
    expect(result[0].periods).toEqual(['3개월']);
  });

  it('스페이스만 선택 (채널 미선택) — space target만, space period DEFAULT 자동 push', () => {
    const result = groupChannelTalkSyncDispatch([channelA], new Set(), new Set(['sp-1']), {}, {});
    expect(result).toHaveLength(1);
    expect(result[0].targets).toEqual([{ target_type: 'space', target_id: 'sp-1' }]);
    // 명시 안 된 space period는 DEFAULT_PERIOD ('전체')로 push 됨
    expect(result[0].periods).toEqual(['전체']);
  });

  it('스페이스 period 명시 설정 시 그대로 사용', () => {
    const result = groupChannelTalkSyncDispatch(
      [channelA],
      new Set(),
      new Set(['sp-1']),
      {},
      { 'sp-1': '1년' },
    );
    expect(result[0].periods).toEqual(['1년']);
  });

  it('채널 + 스페이스 혼합 — 각각의 period 모두 수집', () => {
    const result = groupChannelTalkSyncDispatch(
      [channelA],
      new Set(['ch-a']),
      new Set(['sp-1']),
      { 'ch-a': '6개월' },
      { 'sp-1': '1개월' },
    );
    expect(result[0].targets).toHaveLength(2);
    expect(result[0].periods).toEqual(['6개월', '1개월']);
  });

  it('빈 그룹 (선택 없는 채널) 자동 제외 — 다중 채널', () => {
    const result = groupChannelTalkSyncDispatch(
      [channelA, channelB],
      new Set(['ch-b']),
      new Set(),
      { 'ch-b': '3개월' },
      {},
    );
    expect(result).toHaveLength(1);
    expect(result[0].channel.channel_id).toBe('ch-b');
  });

  it('스페이스가 0개인 채널만 선택 — channel target 1개, period 1개', () => {
    const channelNoSpaces: ChannelTalkChannel = {
      channel_id: 'ch-x',
      display_name: 'Channel X',
      document_spaces: [],
    };
    const result = groupChannelTalkSyncDispatch(
      [channelNoSpaces],
      new Set(['ch-x']),
      new Set(),
      { 'ch-x': '6개월' },
      {},
    );
    expect(result).toHaveLength(1);
    expect(result[0].targets).toEqual([{ target_type: 'channel', target_id: 'ch-x' }]);
    expect(result[0].periods).toEqual(['6개월']);
  });

  it('스페이스 미설정 시 채널 기간을 상속하지 않음 (독립 모델)', () => {
    // 채널 미선택, 스페이스 선택, 채널 period는 '3개월'로 명시했지만
    // space period에는 영향 없어야 함 → space period는 DEFAULT '전체'
    const result = groupChannelTalkSyncDispatch(
      [channelA],
      new Set(),
      new Set(['sp-1']),
      { 'ch-a': '3개월' },
      {},
    );
    expect(result[0].periods).toEqual(['전체']);
  });
});

describe('pickSyncDays', () => {
  it('빈 배열은 null (백엔드 기본값 사용)', () => {
    expect(pickSyncDays([])).toBeNull();
  });

  it('가장 긴 period 채택', () => {
    expect(pickSyncDays(['1개월', '3개월', '1년'] as Period[])).toBe(365);
  });

  it('전체가 포함되면 null', () => {
    expect(pickSyncDays(['3개월', '전체'] as Period[])).toBeNull();
  });
});
