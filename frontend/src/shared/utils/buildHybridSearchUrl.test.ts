import { describe, expect, it } from 'vitest';

import { buildHybridSearchUrl } from './buildHybridSearchUrl';

function paramsOf(url: string) {
  return new URL(url, 'http://localhost').searchParams;
}

describe('buildHybridSearchUrl', () => {
  it('serializes query, tools, date range, and smart filter', () => {
    const url = buildHybridSearchUrl({
      query: '회의록',
      sources: ['slack', 'jira'],
      dateRange: { from: new Date(2026, 4, 13), to: new Date(2026, 4, 14) },
      smartFilter: true,
    });

    expect(url).not.toBeNull();
    expect(url!.startsWith('/hybrid-search?')).toBe(true);

    const params = paramsOf(url!);
    expect(params.get('q')).toBe('회의록');
    expect(params.get('tools')).toBe('slack,jira');
    expect(params.get('start')).toBe('2026-05-13');
    expect(params.get('end')).toBe('2026-05-14');
    expect(params.get('smart_filter')).toBe('true');
  });

  it('trims the query and omits tools when no source is selected', () => {
    const url = buildHybridSearchUrl({ query: '  기본 검색  ', sources: [], smartFilter: false });

    const params = paramsOf(url!);
    expect(params.get('q')).toBe('기본 검색');
    expect(params.has('tools')).toBe(false);
    expect(params.get('smart_filter')).toBe('false');
  });

  it('omits start/end when no date range is given', () => {
    const url = buildHybridSearchUrl({ query: '롤백', smartFilter: true });

    const params = paramsOf(url!);
    expect(params.has('start')).toBe(false);
    expect(params.has('end')).toBe(false);
  });

  it('falls back to end=start when the range has no end', () => {
    const url = buildHybridSearchUrl({
      query: '롤백',
      dateRange: { from: new Date(2026, 4, 13), to: undefined },
      smartFilter: true,
    });

    const params = paramsOf(url!);
    expect(params.get('start')).toBe('2026-05-13');
    expect(params.get('end')).toBe('2026-05-13');
  });

  it('returns null for a blank query', () => {
    expect(buildHybridSearchUrl({ query: '   ', smartFilter: true })).toBeNull();
    expect(buildHybridSearchUrl({ query: '', smartFilter: false })).toBeNull();
  });
});
