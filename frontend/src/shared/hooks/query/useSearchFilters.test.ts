import { act, renderHook } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { useSearchFilters } from './useSearchFilters';

describe('useSearchFilters', () => {
  it('selectedSources 초기값은 빈 배열', () => {
    const { result } = renderHook(() => useSearchFilters());
    expect(result.current.selectedSources).toEqual([]);
  });

  it('setSelectedSources로 channel_talk 포함 5개 소스를 모두 유지', () => {
    const { result } = renderHook(() => useSearchFilters());
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

  it('setSelectedSources로 channel_talk 단독 선택 가능', () => {
    const { result } = renderHook(() => useSearchFilters());
    act(() => result.current.setSelectedSources(['channel_talk']));
    expect(result.current.selectedSources).toEqual(['channel_talk']);
  });
});
