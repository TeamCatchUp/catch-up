import { describe, expect, it } from 'vitest';

import { formatHistoryDate } from './embeddingUtils';

/**
 * "실행 시각" 형식은 디자인 계약이다 — Figma `17169:75993`의 `2026.03.18 00:00 PM`.
 * 리디자인 전 형식(`2026.03.18 (수) 09:52 PM`)의 요일이 빠졌는지 고정한다.
 */
describe('formatHistoryDate', () => {
  it('ISO datetime을 "YYYY.MM.DD hh:mm AM/PM"으로 만든다 — 요일은 넣지 않는다', () => {
    const result = formatHistoryDate(new Date(2026, 2, 18, 21, 52).toISOString());
    expect(result).toBe('2026.03.18 09:52 PM');
    expect(result).not.toMatch(/[()]/);
  });

  it('월·일·시·분을 두 자리로 채운다', () => {
    expect(formatHistoryDate(new Date(2026, 0, 5, 9, 7).toISOString())).toBe('2026.01.05 09:07 AM');
  });

  it('자정과 정오는 12시로 표기한다', () => {
    expect(formatHistoryDate(new Date(2026, 2, 18, 0, 0).toISOString())).toBe('2026.03.18 12:00 AM');
    expect(formatHistoryDate(new Date(2026, 2, 18, 12, 0).toISOString())).toBe('2026.03.18 12:00 PM');
  });

  it('"YYYY-MM-DD"는 타임존 변환 없이 그대로 읽는다', () => {
    expect(formatHistoryDate('2026-03-18')).toBe('2026.03.18 12:00 AM');
  });

  it('빈 문자열과 파싱 불가 값은 그대로 흘린다', () => {
    expect(formatHistoryDate('')).toBe('');
    expect(formatHistoryDate('not-a-date')).toBe('not-a-date');
  });
});
