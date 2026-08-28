import { describe, expect, it } from 'vitest';

import { syncIntervalFromHours } from '../types/channelTalkModel';
import type { ChannelTalkConnectionStatusResponse } from '../types/connectionStatusApi';
import { deriveChannelTalkInitialState } from './deriveChannelTalkInitialState';

const response = (
  items: ChannelTalkConnectionStatusResponse['items'],
): ChannelTalkConnectionStatusResponse => ({
  vendor: 'channel_talk',
  connection_type: 'credential',
  connected: items.length > 0,
  count: items.length,
  items,
});

const channelItem = (id: string) => ({
  id,
  name: `채널 ${id}`,
  connected_at: null,
  metadata: {
    credential_type: 'channel' as const,
    last_verified_at: null,
    webhook_token_configured: true,
  },
});

const spaceItem = (id: string, channelId: string, pollingCycleHours: number) => ({
  id,
  name: `스페이스 ${id}`,
  connected_at: null,
  metadata: {
    credential_type: 'document_space' as const,
    channel_id: channelId,
    association_status: 'api_verified',
    last_verified_at: null,
    polling_cycle_hours: pollingCycleHours,
  },
});

describe('deriveChannelTalkInitialState — 동기화 주기 hydrate', () => {
  it('서버에 저장된 polling_cycle_hours로 syncInterval을 채운다', () => {
    const state = deriveChannelTalkInitialState(
      response([channelItem('ch-1'), spaceItem('sp-1', 'ch-1', 24)]),
    );
    expect(state.channels[0].documentSpaces[0].syncInterval).toBe('24hour');
  });

  it('옵션에 없는 값은 가장 가까운 옵션으로 보존한다', () => {
    const state = deriveChannelTalkInitialState(
      response([channelItem('ch-1'), spaceItem('sp-1', 'ch-1', 48)]),
    );
    expect(state.channels[0].documentSpaces[0].syncInterval).toBe('24hour');
  });
});

describe('syncIntervalFromHours', () => {
  it('정확히 일치하는 옵션을 돌려준다', () => {
    expect(syncIntervalFromHours(1)).toBe('1hour');
    expect(syncIntervalFromHours(6)).toBe('6hour');
    expect(syncIntervalFromHours(12)).toBe('12hour');
    expect(syncIntervalFromHours(24)).toBe('24hour');
  });

  it('옵션 밖의 값은 가장 가까운 옵션으로 매핑한다', () => {
    expect(syncIntervalFromHours(3)).toBe('1hour');
    expect(syncIntervalFromHours(8)).toBe('6hour');
    expect(syncIntervalFromHours(168)).toBe('24hour');
  });
});
