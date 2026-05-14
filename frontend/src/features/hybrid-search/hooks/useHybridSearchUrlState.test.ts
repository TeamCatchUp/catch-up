import { act,renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useHybridSearchUrlState } from './useHybridSearchUrlState';

const mockReplace = vi.fn();
const mockSearchParams = new URLSearchParams();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: mockReplace, push: vi.fn() }),
  useSearchParams: () => mockSearchParams,
  usePathname: () => '/hybrid-search',
}));

beforeEach(() => {
  mockReplace.mockClear();
  for (const key of Array.from(mockSearchParams.keys())) mockSearchParams.delete(key);
});

describe('useHybridSearchUrlState', () => {
  it('URL 비어있을 때 keyword=빈문자, tools=[], page=1', () => {
    const { result } = renderHook(() => useHybridSearchUrlState());
    expect(result.current.keyword).toBe('');
    expect(result.current.tools).toEqual([]);
    expect(result.current.page).toBe(1);
  });

  it('?q=foo&tools=jira,slack&page=2 파싱', () => {
    mockSearchParams.set('q', 'foo');
    mockSearchParams.set('tools', 'jira,slack');
    mockSearchParams.set('page', '2');
    const { result } = renderHook(() => useHybridSearchUrlState());
    expect(result.current.keyword).toBe('foo');
    expect(result.current.tools).toEqual(['jira', 'slack']);
    expect(result.current.page).toBe(2);
  });

  it('?tools=hack 화이트리스트 외 값 제외', () => {
    mockSearchParams.set('tools', 'jira,hack,slack');
    const { result } = renderHook(() => useHybridSearchUrlState());
    expect(result.current.tools).toEqual(['jira', 'slack']);
  });

  it('?page=abc NaN → page=1 fallback', () => {
    mockSearchParams.set('page', 'abc');
    const { result } = renderHook(() => useHybridSearchUrlState());
    expect(result.current.page).toBe(1);
  });

  it('setKeyword 호출 시 page 리셋 + URL replace', () => {
    mockSearchParams.set('q', 'old');
    mockSearchParams.set('page', '5');
    const { result } = renderHook(() => useHybridSearchUrlState());
    act(() => result.current.setKeyword('new'));
    expect(mockReplace).toHaveBeenCalledTimes(1);
    const url = mockReplace.mock.calls[0]![0] as string;
    expect(url).toContain('q=new');
    expect(url).not.toContain('page=');
  });

  it('setTools([\"jira\"]) → page 리셋', () => {
    mockSearchParams.set('q', 'x');
    mockSearchParams.set('page', '3');
    const { result } = renderHook(() => useHybridSearchUrlState());
    act(() => result.current.setTools(['jira']));
    const url = mockReplace.mock.calls[0]![0] as string;
    expect(url).toContain('tools=jira');
    expect(url).not.toContain('page=');
  });

  it('setTools([]) → tools 파라미터 제거', () => {
    mockSearchParams.set('q', 'x');
    mockSearchParams.set('tools', 'jira');
    const { result } = renderHook(() => useHybridSearchUrlState());
    act(() => result.current.setTools([]));
    const url = mockReplace.mock.calls[0]![0] as string;
    expect(url).not.toContain('tools=');
  });

  it('setPage(3) → page=3 유지, 다른 파라미터 보존', () => {
    mockSearchParams.set('q', 'x');
    mockSearchParams.set('tools', 'jira');
    const { result } = renderHook(() => useHybridSearchUrlState());
    act(() => result.current.setPage(3));
    const url = mockReplace.mock.calls[0]![0] as string;
    expect(url).toContain('q=x');
    expect(url).toContain('tools=jira');
    expect(url).toContain('page=3');
  });

  it('URL의 ?active=jira 파싱', () => {
    mockSearchParams.set('q', 'foo');
    mockSearchParams.set('tools', 'jira,slack');
    mockSearchParams.set('active', 'jira');
    const { result } = renderHook(() => useHybridSearchUrlState());
    expect(result.current.active).toBe('jira');
  });

  it('?active=hack (화이트리스트 외) → all fallback', () => {
    mockSearchParams.set('active', 'hack');
    const { result } = renderHook(() => useHybridSearchUrlState());
    expect(result.current.active).toBe('all');
  });

  it('?active 없음 → all', () => {
    const { result } = renderHook(() => useHybridSearchUrlState());
    expect(result.current.active).toBe('all');
  });

  it('setActive("jira") → URL에 ?active=jira 추가, page 리셋', () => {
    mockSearchParams.set('q', 'x');
    mockSearchParams.set('tools', 'jira,slack');
    mockSearchParams.set('page', '2');
    const { result } = renderHook(() => useHybridSearchUrlState());
    act(() => result.current.setActive('jira'));
    const url = mockReplace.mock.calls[0]![0] as string;
    expect(url).toContain('active=jira');
    expect(url).toContain('tools=jira%2Cslack');
    expect(url).not.toContain('page=');
  });

  it('setActive("all") → URL에서 active 제거', () => {
    mockSearchParams.set('q', 'x');
    mockSearchParams.set('active', 'jira');
    const { result } = renderHook(() => useHybridSearchUrlState());
    act(() => result.current.setActive('all'));
    const url = mockReplace.mock.calls[0]![0] as string;
    expect(url).not.toContain('active=');
  });

  it('setKeyword 호출 시 active도 함께 reset', () => {
    mockSearchParams.set('q', 'old');
    mockSearchParams.set('tools', 'jira,slack');
    mockSearchParams.set('active', 'jira');
    mockSearchParams.set('page', '3');
    const { result } = renderHook(() => useHybridSearchUrlState());
    act(() => result.current.setKeyword('new'));
    const url = mockReplace.mock.calls[0]![0] as string;
    expect(url).toContain('q=new');
    expect(url).toContain('tools=jira%2Cslack'); // tools는 유지
    expect(url).not.toContain('active='); // active reset
    expect(url).not.toContain('page='); // page reset
  });

  it('setTools 호출 시 active도 함께 reset', () => {
    mockSearchParams.set('q', 'x');
    mockSearchParams.set('active', 'jira');
    const { result } = renderHook(() => useHybridSearchUrlState());
    act(() => result.current.setTools(['confluence']));
    const url = mockReplace.mock.calls[0]![0] as string;
    expect(url).toContain('tools=confluence');
    expect(url).not.toContain('active=');
  });
});
