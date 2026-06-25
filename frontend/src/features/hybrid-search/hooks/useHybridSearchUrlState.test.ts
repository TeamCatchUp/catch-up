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

  it('smart_filter 파라미터가 없으면 기본 ON으로 파싱한다', () => {
    const { result } = renderHook(() => useHybridSearchUrlState());
    expect(result.current.smartFilter).toBe(true);
  });

  it('?smart_filter=false 는 OFF로 파싱한다', () => {
    mockSearchParams.set('smart_filter', 'false');
    const { result } = renderHook(() => useHybridSearchUrlState());
    expect(result.current.smartFilter).toBe(false);
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

  it('?start=2026-05-01&end=2026-05-19 → dateRange 파싱', () => {
    mockSearchParams.set('start', '2026-05-01');
    mockSearchParams.set('end', '2026-05-19');
    const { result } = renderHook(() => useHybridSearchUrlState());
    expect(result.current.dateRange?.from).toEqual(new Date(2026, 4, 1));
    expect(result.current.dateRange?.to).toEqual(new Date(2026, 4, 19));
  });

  it('start 파라미터 없으면 dateRange는 undefined', () => {
    const { result } = renderHook(() => useHybridSearchUrlState());
    expect(result.current.dateRange).toBeUndefined();
  });

  it('commitSearch → keyword + tools + 기간 동시 갱신 (단일 replace)', () => {
    mockSearchParams.set('q', 'old');
    mockSearchParams.set('tools', 'jira');
    const { result } = renderHook(() => useHybridSearchUrlState());
    act(() =>
      result.current.commitSearch(
        'new',
        ['slack', 'github'],
        {
          from: new Date(2026, 4, 1),
          to: new Date(2026, 4, 19),
        },
        true,
      ),
    );
    expect(mockReplace).toHaveBeenCalledTimes(1);
    const url = mockReplace.mock.calls[0]![0] as string;
    expect(url).toContain('q=new');
    expect(url).toContain('tools=slack%2Cgithub');
    expect(url).toContain('start=2026-05-01');
    expect(url).toContain('end=2026-05-19');
    expect(url).toContain('smart_filter=true');
  });

  it('commitSearch("", [], undefined) → q·tools·start·end 모두 제거', () => {
    mockSearchParams.set('q', 'x');
    mockSearchParams.set('tools', 'jira');
    mockSearchParams.set('start', '2026-05-01');
    mockSearchParams.set('end', '2026-05-19');
    const { result } = renderHook(() => useHybridSearchUrlState());
    act(() => result.current.commitSearch('', [], undefined, false));
    const url = mockReplace.mock.calls[0]![0] as string;
    expect(url).not.toContain('q=');
    expect(url).not.toContain('tools=');
    expect(url).not.toContain('start=');
    expect(url).not.toContain('end=');
    expect(url).toContain('smart_filter=false');
  });

  it('commitSearch는 smart_filter=true를 항상 명시한다', () => {
    const { result } = renderHook(() => useHybridSearchUrlState());
    act(() => result.current.commitSearch('new', [], undefined, true));
    const url = mockReplace.mock.calls[0]![0] as string;
    expect(url).toContain('q=new');
    expect(url).toContain('smart_filter=true');
  });

  it('commitSearch는 smart_filter=false를 항상 명시한다', () => {
    const { result } = renderHook(() => useHybridSearchUrlState());
    act(() => result.current.commitSearch('new', [], undefined, false));
    const url = mockReplace.mock.calls[0]![0] as string;
    expect(url).toContain('q=new');
    expect(url).toContain('smart_filter=false');
  });
});
