import { act, renderHook } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import useRagFilters from './useRagFilters';

describe('useRagFilters', () => {
  it('initialSources 없으면 빈 배열 + 필터 닫힘', () => {
    const { result } = renderHook(() => useRagFilters());
    expect(result.current.selectedSources).toEqual([]);
    expect(result.current.isFilterOpen).toBe(false);
  });

  it('initialSources가 있으면 selectedSources 반영 + 필터 자동 열림', () => {
    const { result } = renderHook(() => useRagFilters({ initialSources: ['jira', 'channel_talk'] }));
    expect(result.current.selectedSources).toEqual(['jira', 'channel_talk']);
    expect(result.current.isFilterOpen).toBe(true);
  });

  it('setSelectedSources로 channel_talk 포함 5개 소스를 모두 유지', () => {
    const { result } = renderHook(() => useRagFilters());
    act(() => {
      result.current.setSelectedSources(['confluence', 'jira', 'slack', 'github', 'channel_talk']);
    });
    expect(result.current.selectedSources).toEqual([
      'confluence',
      'jira',
      'slack',
      'github',
      'channel_talk',
    ]);
  });

  it('toggleFilter로 isFilterOpen 토글', () => {
    const { result } = renderHook(() => useRagFilters());
    act(() => result.current.toggleFilter());
    expect(result.current.isFilterOpen).toBe(true);
    act(() => result.current.toggleFilter());
    expect(result.current.isFilterOpen).toBe(false);
  });
});
