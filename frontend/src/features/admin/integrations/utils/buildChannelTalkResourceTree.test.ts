import { describe, expect, it } from 'vitest';

import type { AdminConnectorTargetRangeResponse } from '../types/syncModel';
import { buildChannelTalkResourceTree } from './buildChannelTalkResourceTree';

const target = (over: Partial<AdminConnectorTargetRangeResponse>): AdminConnectorTargetRangeResponse => ({
  scope_id: '229395',
  target_id: '229395',
  target_name: '이름',
  event_id: 'evt',
  sync_status: 'success',
  last_succeeded_at: null,
  last_failed_at: null,
  oldest: null,
  latest: null,
  ...over,
});

describe('buildChannelTalkResourceTree', () => {
  /** 2026-08-04 `GET /admin/connector/status?source=channel_talk` 실측 응답 */
  const REAL = [
    target({ target_type: 'space', target_id: '16957', target_name: 'Catch Up Guide', oldest: '2026-04-30', latest: '2026-07-01' }),
    target({ target_type: 'channel', target_id: '229395', target_name: 'Catch Up | 캐치업', oldest: '2026-04-15', latest: '2026-07-23' }),
    target({ target_type: 'space', target_id: '18234', target_name: '도큐먼트 스페이스 2' }),
  ];

  it('채널을 최상위로 올리고 같은 scope의 space를 children으로 단다', () => {
    const tree = buildChannelTalkResourceTree(REAL);

    expect(tree).toHaveLength(1);
    expect(tree[0].name).toBe('Catch Up | 캐치업');
    expect(tree[0].dateRange).toBe('2026.04.15 - 2026.07.23');
    expect(tree[0].children?.map((c) => c.name)).toEqual(['Catch Up Guide', '도큐먼트 스페이스 2']);
  });

  it('범위가 없는 space는 "-"로 낸다', () => {
    const tree = buildChannelTalkResourceTree(REAL);
    expect(tree[0].children?.[1].dateRange).toBe('-');
  });

  it('id는 scope와 target을 합쳐 유일하게 만든다 — 이름은 겹칠 수 있다', () => {
    const tree = buildChannelTalkResourceTree(REAL);
    expect(tree[0].id).toBe('229395-229395');
    expect(tree[0].children?.map((c) => c.id)).toEqual(['229395-16957', '229395-18234']);
  });

  it('채널이 응답 뒤쪽에 와도 순서에 기대지 않는다', () => {
    const reversed = buildChannelTalkResourceTree([...REAL].reverse());
    expect(reversed).toHaveLength(1);
    expect(reversed[0].name).toBe('Catch Up | 캐치업');
    expect(reversed[0].children).toHaveLength(2);
  });

  it('채널 순서는 그 scope가 처음 등장한 위치를 따른다', () => {
    const tree = buildChannelTalkResourceTree([
      target({ scope_id: 'B', target_id: 'b-space', target_type: 'space', target_name: 'B의 스페이스' }),
      target({ scope_id: 'A', target_id: 'A', target_type: 'channel', target_name: '채널 A' }),
      target({ scope_id: 'B', target_id: 'B', target_type: 'channel', target_name: '채널 B' }),
    ]);
    expect(tree.map((r) => r.name)).toEqual(['채널 B', '채널 A']);
  });

  it('target_type이 없는 구 응답은 target_id === scope_id 로 채널을 가린다', () => {
    const tree = buildChannelTalkResourceTree([
      target({ target_id: '16957', target_name: 'Catch Up Guide' }),
      target({ target_id: '229395', target_name: 'Catch Up | 캐치업' }),
    ]);
    expect(tree[0].name).toBe('Catch Up | 캐치업');
    expect(tree[0].children?.map((c) => c.name)).toEqual(['Catch Up Guide']);
  });

  it('채널 target이 없으면 space를 최상위로 올린다 — 목록에서 빠뜨리지 않는다', () => {
    const tree = buildChannelTalkResourceTree([
      target({ target_type: 'space', target_id: '16957', target_name: '고아 스페이스' }),
    ]);
    expect(tree.map((r) => r.name)).toEqual(['고아 스페이스']);
    expect(tree[0].children).toBeUndefined();
  });

  it('빈 배열은 빈 배열', () => {
    expect(buildChannelTalkResourceTree([])).toEqual([]);
  });
});
