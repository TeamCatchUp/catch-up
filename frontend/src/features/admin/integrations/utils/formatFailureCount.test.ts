import { describe, expect, it } from 'vitest';

import { formatFailureCount } from './formatFailureCount';

describe('formatFailureCount', () => {
  it('천 단위 콤마를 넣는다', () => {
    expect(formatFailureCount(0)).toBe('0건');
    expect(formatFailureCount(10)).toBe('10건');
    expect(formatFailureCount(9999)).toBe('9,999건');
    expect(formatFailureCount(49999)).toBe('49,999건');
  });

  it('정확히 50,000이면 +를 붙이지 않는다', () => {
    expect(formatFailureCount(50000)).toBe('50,000건');
  });

  it('50,000을 넘으면 50,000+건으로 고정한다', () => {
    expect(formatFailureCount(50001)).toBe('50,000+건');
    expect(formatFailureCount(123456)).toBe('50,000+건');
  });

  it('음수와 소수는 0 이상 정수로 보정한다', () => {
    expect(formatFailureCount(-5)).toBe('0건');
    expect(formatFailureCount(10.7)).toBe('10건');
  });
});
