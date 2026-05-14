import { act, renderHook } from '@testing-library/react';
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
  it('URL 비어있을 때 keyword=빈문자, tools=[]', () => {
    const { result } = renderHook(() => useHybridSearchUrlState());
    expect(result.current.keyword).toBe('');
    expect(result.current.tools).toEqual([]);
  });

  it('?q=foo&tools=jira,slack 파싱', () => {
    mockSearchParams.set('q', 'foo');
    mockSearchParams.set('tools', 'jira,slack');
    const { result } = renderHook(() => useHybridSearchUrlState());
    expect(result.current.keyword).toBe('foo');
    expect(result.current.tools).toEqual(['jira', 'slack']);
  });

  it('?tools=hack 화이트리스트 외 값 제외', () => {
    mockSearchParams.set('tools', 'jira,hack,slack');
    const { result } = renderHook(() => useHybridSearchUrlState());
    expect(result.current.tools).toEqual(['jira', 'slack']);
  });

  it('setKeyword 호출 시 URL replace, tools 유지', () => {
    mockSearchParams.set('q', 'old');
    mockSearchParams.set('tools', 'jira');
    const { result } = renderHook(() => useHybridSearchUrlState());
    act(() => result.current.setKeyword('new'));
    expect(mockReplace).toHaveBeenCalledTimes(1);
    const url = mockReplace.mock.calls[0]![0] as string;
    expect(url).toContain('q=new');
    expect(url).toContain('tools=jira');
  });

  it('setKeyword("") → q 파라미터 제거', () => {
    mockSearchParams.set('q', 'old');
    const { result } = renderHook(() => useHybridSearchUrlState());
    act(() => result.current.setKeyword(''));
    const url = mockReplace.mock.calls[0]![0] as string;
    expect(url).not.toContain('q=');
  });

  it('setTools(["jira"]) → ?tools=jira', () => {
    mockSearchParams.set('q', 'x');
    const { result } = renderHook(() => useHybridSearchUrlState());
    act(() => result.current.setTools(['jira']));
    const url = mockReplace.mock.calls[0]![0] as string;
    expect(url).toContain('tools=jira');
  });

  it('setTools([]) → tools 파라미터 제거', () => {
    mockSearchParams.set('q', 'x');
    mockSearchParams.set('tools', 'jira');
    const { result } = renderHook(() => useHybridSearchUrlState());
    act(() => result.current.setTools([]));
    const url = mockReplace.mock.calls[0]![0] as string;
    expect(url).not.toContain('tools=');
  });

  it('setKeywordAndTools → keyword + tools 동시 갱신 (단일 replace)', () => {
    mockSearchParams.set('q', 'old');
    mockSearchParams.set('tools', 'jira');
    const { result } = renderHook(() => useHybridSearchUrlState());
    act(() => result.current.setKeywordAndTools('new', ['slack', 'github']));
    expect(mockReplace).toHaveBeenCalledTimes(1);
    const url = mockReplace.mock.calls[0]![0] as string;
    expect(url).toContain('q=new');
    expect(url).toContain('tools=slack%2Cgithub');
  });

  it('setKeywordAndTools("", []) → 두 파라미터 모두 제거', () => {
    mockSearchParams.set('q', 'x');
    mockSearchParams.set('tools', 'jira');
    const { result } = renderHook(() => useHybridSearchUrlState());
    act(() => result.current.setKeywordAndTools('', []));
    const url = mockReplace.mock.calls[0]![0] as string;
    expect(url).not.toContain('q=');
    expect(url).not.toContain('tools=');
  });
});
