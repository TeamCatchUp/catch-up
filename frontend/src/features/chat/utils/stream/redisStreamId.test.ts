import { describe, expect, it } from 'vitest';

import { compareRedisStreamIds, isRedisStreamIdAtOrBefore } from './redisStreamId';

describe('compareRedisStreamIds', () => {
  it('orders by millisecond part first', () => {
    expect(compareRedisStreamIds('9-99', '10-0')).toBeLessThan(0);
  });

  it('orders by sequence part when millisecond part matches', () => {
    expect(compareRedisStreamIds('10-1', '10-2')).toBeLessThan(0);
    expect(compareRedisStreamIds('10-2', '10-2')).toBe(0);
    expect(compareRedisStreamIds('10-3', '10-2')).toBeGreaterThan(0);
  });
});

describe('isRedisStreamIdAtOrBefore', () => {
  it('returns true only when id is at or before cutoff', () => {
    expect(isRedisStreamIdAtOrBefore('10-1', '10-2')).toBe(true);
    expect(isRedisStreamIdAtOrBefore('10-2', '10-2')).toBe(true);
    expect(isRedisStreamIdAtOrBefore('10-3', '10-2')).toBe(false);
  });

  it('returns false when id or cutoff is missing', () => {
    expect(isRedisStreamIdAtOrBefore(undefined, '10-2')).toBe(false);
    expect(isRedisStreamIdAtOrBefore('10-1', null)).toBe(false);
  });
});
