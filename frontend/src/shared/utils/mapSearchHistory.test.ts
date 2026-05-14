import { describe, expect, it } from 'vitest';

import { mapSearchHistory } from './mapSearchHistory';

describe('mapSearchHistory', () => {
  it('id를 string으로 변환한다', () => {
    const result = mapSearchHistory({ id: 42, query: '결제 롤백', created_at: '2026-05-13T09:14:23Z' });
    expect(result.id).toBe('42');
  });

  it('query를 그대로 전달한다', () => {
    const result = mapSearchHistory({ id: 1, query: '지난주 결제 롤백', created_at: '2026-05-13T09:14:23Z' });
    expect(result.query).toBe('지난주 결제 롤백');
  });

  it('created_at ISO 문자열을 Date 객체로 변환한다', () => {
    const result = mapSearchHistory({ id: 1, query: 'q', created_at: '2026-05-13T09:14:23.000Z' });
    expect(result.createdAt).toBeInstanceOf(Date);
    expect(result.createdAt.toISOString()).toBe('2026-05-13T09:14:23.000Z');
  });
});
