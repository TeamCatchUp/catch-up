import { describe, expect, it } from 'vitest';

import { formatEmbeddingDate, formatEmbeddingRange, formatHistoryDate } from './embeddingUtils';

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

/**
 * "데이터 범위" 형식도 디자인 계약이다 — Figma `17169:75787`의
 * `2000.00.00 - 2000.00.00`. 리디자인 전 형식("2026. 3. 6. ~ 2026. 5. 4.")은
 * 공백·0채움·구분자 세 군데가 달랐다.
 */
describe('formatEmbeddingDate', () => {
  it('0을 채운 "YYYY.MM.DD"로 만든다 — 공백과 끝 마침표를 넣지 않는다', () => {
    const result = formatEmbeddingDate(new Date(2026, 2, 6).toISOString());
    expect(result).toBe('2026.03.06');
    expect(result).not.toContain(' ');
    expect(result.endsWith('.')).toBe(false);
  });

  it('null과 파싱 불가 값은 각각 빈 문자열·원문으로 흘린다', () => {
    expect(formatEmbeddingDate(null)).toBe('');
    expect(formatEmbeddingDate('not-a-date')).toBe('not-a-date');
  });
});

describe('formatEmbeddingRange', () => {
  const march6 = new Date(2026, 2, 6).toISOString();
  const may4 = new Date(2026, 4, 4).toISOString();

  it('하이픈으로 두 날짜를 잇는다 — 물결표가 아니다', () => {
    expect(formatEmbeddingRange(march6, may4)).toBe('2026.03.06 - 2026.05.04');
  });

  it('한쪽만 있으면 구분자 없이 그 날짜만 낸다', () => {
    expect(formatEmbeddingRange(null, may4)).toBe('2026.05.04');
    expect(formatEmbeddingRange(march6, null)).toBe('2026.03.06');
  });

  it('둘 다 없으면 "-"', () => {
    expect(formatEmbeddingRange(null, null)).toBe('-');
  });
});
