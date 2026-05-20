import { describe, expect, it } from 'vitest';

import type { SourceResponseApi } from '@/shared/types/sourceApi';

import { applySlackDateFallback } from './applySlackDateFallback';

// 최소 필드만 채우고 SourceResponseApi로 단언 — sort/normalize는 이 헬퍼와 무관한 필드라 OK.
function makeItem(partial: Partial<SourceResponseApi> & Pick<SourceResponseApi, 'source'>): SourceResponseApi {
  return {
    id: 'x',
    title: '',
    text: '',
    entity_type: 'message',
    ...partial,
  } as SourceResponseApi;
}

describe('applySlackDateFallback', () => {
  it('Slack 항목 updated_at 누락 시 created_at으로 폴백', () => {
    const items = [makeItem({ source: 'slack', created_at: '2026-05-10T00:00:00Z', updated_at: null })];
    expect(applySlackDateFallback(items)[0].updated_at).toBe('2026-05-10T00:00:00Z');
  });

  it('Slack 항목 updated_at 있으면 그대로 유지', () => {
    const items = [makeItem({ source: 'slack', created_at: '2026-05-01T00:00:00Z', updated_at: '2026-05-09T00:00:00Z' })];
    expect(applySlackDateFallback(items)[0].updated_at).toBe('2026-05-09T00:00:00Z');
  });

  it('Slack 항목 updated_at·created_at 둘 다 없으면 그대로', () => {
    const items = [makeItem({ source: 'slack', updated_at: null, created_at: null })];
    expect(applySlackDateFallback(items)[0].updated_at).toBeNull();
  });

  it('Slack 외 소스는 updated_at 누락이어도 건드리지 않음', () => {
    const items = [
      makeItem({ source: 'github', created_at: '2026-05-01T00:00:00Z', updated_at: null }),
      makeItem({ source: 'jira', created_at: '2026-05-02T00:00:00Z', updated_at: null }),
    ];
    const result = applySlackDateFallback(items);
    expect(result[0].updated_at).toBeNull();
    expect(result[1].updated_at).toBeNull();
  });

  it('원본 배열을 변경하지 않는다', () => {
    const items = [makeItem({ source: 'slack', created_at: '2026-05-10T00:00:00Z', updated_at: null })];
    const before = JSON.stringify(items);
    applySlackDateFallback(items);
    expect(JSON.stringify(items)).toBe(before);
  });
});
