import { describe, expect, it } from 'vitest';

import type { OriginalMessageItem } from '@/features/hybrid-search/types/originalApi';

import { groupMessagesByDate } from './groupMessagesByDate';

// 최소 필드만 채운 메시지 — 그룹핑은 id/created_at 만 본다.
function makeMessage(id: string, createdAt: string | null): OriginalMessageItem {
  return {
    id,
    type: 'message',
    visibility: 'public',
    author: null,
    contents: [],
    created_at: createdAt,
    updated_at: null,
  };
}

describe('groupMessagesByDate', () => {
  it('여러 날짜를 캘린더 날짜별로 묶고 등장 순서를 유지한다', () => {
    const items = [
      makeMessage('a', '2026-05-20T09:30:00+09:00'),
      makeMessage('b', '2026-05-20T18:00:00+09:00'),
      makeMessage('c', '2026-05-21T10:05:00+09:00'),
      makeMessage('d', '2026-05-22T11:20:00+09:00'),
    ];

    const groups = groupMessagesByDate(items);

    expect(groups).toHaveLength(3);
    expect(groups[0].date).toBe('2026-05-20');
    expect(groups[0].items.map((m) => m.id)).toEqual(['a', 'b']);
    expect(groups[1].date).toBe('2026-05-21');
    expect(groups[1].items.map((m) => m.id)).toEqual(['c']);
    expect(groups[2].date).toBe('2026-05-22');
    expect(groups[2].items.map((m) => m.id)).toEqual(['d']);
  });

  it('같은 날짜 메시지가 떨어져 있어도 한 그룹으로 합친다', () => {
    const items = [
      makeMessage('a', '2026-05-20T09:00:00+09:00'),
      makeMessage('b', '2026-05-21T09:00:00+09:00'),
      makeMessage('c', '2026-05-20T20:00:00+09:00'),
    ];

    const groups = groupMessagesByDate(items);

    expect(groups).toHaveLength(2);
    expect(groups[0].date).toBe('2026-05-20');
    expect(groups[0].items.map((m) => m.id)).toEqual(['a', 'c']);
    expect(groups[1].items.map((m) => m.id)).toEqual(['b']);
  });

  it('하나의 날짜만 있으면 단일 그룹을 반환한다', () => {
    const items = [
      makeMessage('a', '2026-05-20T09:00:00+09:00'),
      makeMessage('b', '2026-05-20T10:00:00+09:00'),
    ];

    const groups = groupMessagesByDate(items);

    expect(groups).toHaveLength(1);
    expect(groups[0].date).toBe('2026-05-20');
    expect(groups[0].items).toHaveLength(2);
  });

  it('빈 배열은 빈 결과를 반환한다', () => {
    expect(groupMessagesByDate([])).toEqual([]);
  });

  it('created_at 이 null 인 메시지는 빈 날짜의 맨 뒤 그룹으로 모은다', () => {
    const items = [
      makeMessage('a', null),
      makeMessage('b', '2026-05-20T09:00:00+09:00'),
      makeMessage('c', null),
    ];

    const groups = groupMessagesByDate(items);

    expect(groups).toHaveLength(2);
    expect(groups[0].date).toBe('2026-05-20');
    expect(groups[0].items.map((m) => m.id)).toEqual(['b']);
    expect(groups[groups.length - 1].date).toBe('');
    expect(groups[groups.length - 1].items.map((m) => m.id)).toEqual(['a', 'c']);
  });

  it('모든 메시지가 created_at null 이면 단일 빈 날짜 그룹', () => {
    const items = [makeMessage('a', null), makeMessage('b', null)];

    const groups = groupMessagesByDate(items);

    expect(groups).toHaveLength(1);
    expect(groups[0].date).toBe('');
    expect(groups[0].items.map((m) => m.id)).toEqual(['a', 'b']);
  });

  it('원본 배열을 변경하지 않는다', () => {
    const items = [
      makeMessage('a', '2026-05-20T09:00:00+09:00'),
      makeMessage('b', null),
    ];
    const before = JSON.stringify(items);

    groupMessagesByDate(items);

    expect(JSON.stringify(items)).toBe(before);
  });
});
