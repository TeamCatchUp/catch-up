import { describe, expect, it } from 'vitest';

import { formatFileSize } from './formatFileSize';

describe('formatFileSize', () => {
  it('undefined / 음수 / Infinity / NaN → null', () => {
    expect(formatFileSize(undefined)).toBeNull();
    expect(formatFileSize(-1)).toBeNull();
    expect(formatFileSize(Infinity)).toBeNull();
    expect(formatFileSize(NaN)).toBeNull();
  });

  it('B 단위 — 소수점 없이 정수로', () => {
    expect(formatFileSize(0)).toBe('0B');
    expect(formatFileSize(1)).toBe('1B');
    expect(formatFileSize(1023)).toBe('1023B');
  });

  it('1024 경계 → KB 로 자동 승급', () => {
    expect(formatFileSize(1024)).toBe('1.0KB');
    expect(formatFileSize(1536)).toBe('1.5KB');
  });

  it('MB / GB / TB 승급', () => {
    expect(formatFileSize(1024 * 1024)).toBe('1.0MB');
    expect(formatFileSize(1024 * 1024 * 1024)).toBe('1.0GB');
    expect(formatFileSize(1024 ** 4)).toBe('1.0TB');
  });

  it('TB 이상은 TB 단위 유지 (cap)', () => {
    expect(formatFileSize(1024 ** 5)).toBe('1024.0TB');
  });
});
