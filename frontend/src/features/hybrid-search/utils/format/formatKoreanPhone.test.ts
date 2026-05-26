import { describe, expect, it } from 'vitest';

import { formatKoreanPhone } from './formatKoreanPhone';

describe('formatKoreanPhone', () => {
  it('모바일 010-XXXX-XXXX 그대로 정규화', () => {
    expect(formatKoreanPhone('010-1234-5678')).toBe('+82 10-1234-5678');
  });

  it('모바일 하이픈 없이 01012345678', () => {
    expect(formatKoreanPhone('01012345678')).toBe('+82 10-1234-5678');
  });

  it('서울 02-XXX-XXXX (subscriber 7자리)', () => {
    expect(formatKoreanPhone('02-789-0123')).toBe('+82 2-789-0123');
  });

  it('서울 02-XXXX-XXXX (subscriber 8자리)', () => {
    expect(formatKoreanPhone('02-1234-5678')).toBe('+82 2-1234-5678');
  });

  it('지역 031-XXXX-XXXX', () => {
    expect(formatKoreanPhone('031-1234-5678')).toBe('+82 31-1234-5678');
  });

  it('이미 +82 prefix 인 경우 정규화', () => {
    expect(formatKoreanPhone('+82 10-1234-5678')).toBe('+82 10-1234-5678');
  });

  it('국제 표기 +821012345678', () => {
    expect(formatKoreanPhone('+821012345678')).toBe('+82 10-1234-5678');
  });

  it('공백 포함', () => {
    expect(formatKoreanPhone('  010 1234 5678  ')).toBe('+82 10-1234-5678');
  });

  it('undefined → undefined', () => {
    expect(formatKoreanPhone(undefined)).toBeUndefined();
  });

  it('null → undefined', () => {
    expect(formatKoreanPhone(null)).toBeUndefined();
  });

  it('빈 문자열 → undefined', () => {
    expect(formatKoreanPhone('')).toBeUndefined();
  });

  it('숫자 없으면 원본 trim 반환', () => {
    expect(formatKoreanPhone('  no digits  ')).toBe('no digits');
  });

  it('예상 외 길이는 원본 trim 반환', () => {
    expect(formatKoreanPhone('1234567')).toBe('1234567');
  });
});
