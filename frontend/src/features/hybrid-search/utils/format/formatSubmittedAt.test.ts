import { describe, expect, it } from 'vitest';

import { formatSubmittedAt } from './formatSubmittedAt';

function localIso(year: number, month: number, day: number, hour: number, minute: number): string {
  return new Date(year, month - 1, day, hour, minute).toISOString();
}

describe('formatSubmittedAt', () => {
  it('undefined / 빈 문자열 / 공백만 → null', () => {
    expect(formatSubmittedAt(undefined)).toBeNull();
    expect(formatSubmittedAt('')).toBeNull();
    expect(formatSubmittedAt('   ')).toBeNull();
  });

  it('파싱 불가 입력은 원문 그대로 (fallback)', () => {
    expect(formatSubmittedAt('not-a-date')).toBe('not-a-date');
  });

  it('유효 ISO → "YYYY-MM-DD HH:MM AM/PM"', () => {
    expect(formatSubmittedAt(localIso(2026, 5, 20, 14, 33))).toBe('2026-05-20 02:33 PM');
  });

  it('자정 / 정오 경계', () => {
    expect(formatSubmittedAt(localIso(2026, 5, 20, 0, 0))).toBe('2026-05-20 12:00 AM');
    expect(formatSubmittedAt(localIso(2026, 5, 20, 12, 0))).toBe('2026-05-20 12:00 PM');
  });
});
