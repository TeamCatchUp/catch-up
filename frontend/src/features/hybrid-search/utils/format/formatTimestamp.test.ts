import { describe, expect, it } from 'vitest';

import { formatTimestamp } from './formatTimestamp';

// new Date(year, month, day, h, m) 는 항상 로컬 시간. toISOString() 으로 UTC 직렬화하면
// formatTimestamp 가 다시 로컬로 파싱할 때 같은 hour/minute 복원 → 타임존 독립적 테스트.
function localIso(year: number, month: number, day: number, hour: number, minute: number): string {
  return new Date(year, month - 1, day, hour, minute).toISOString();
}

describe('formatTimestamp', () => {
  it('자정 0시 → "12:00 AM"', () => {
    expect(formatTimestamp(localIso(2026, 5, 20, 0, 0))).toBe('12:00 AM');
  });

  it('정오 12시 → "12:00 PM"', () => {
    expect(formatTimestamp(localIso(2026, 5, 20, 12, 0))).toBe('12:00 PM');
  });

  it('오전 9:05 → "09:05 AM"', () => {
    expect(formatTimestamp(localIso(2026, 5, 20, 9, 5))).toBe('09:05 AM');
  });

  it('21:45 → "09:45 PM"', () => {
    expect(formatTimestamp(localIso(2026, 5, 20, 21, 45))).toBe('09:45 PM');
  });

  it('파싱 불가 입력은 빈 문자열', () => {
    expect(formatTimestamp('not-a-date')).toBe('');
    expect(formatTimestamp('')).toBe('');
  });
});
