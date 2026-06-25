import type { PropsWithChildren } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';

import { searchHistoryQueries } from '@/shared/queries/searchHistory.queries';
import { server } from '@/test/msw/server';

import { useHybridSearch } from './useHybridSearch';

function makeWrapper(client: QueryClient) {
  return function Wrapper({ children }: PropsWithChildren) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

describe('useHybridSearch', () => {
  it('isSuccess 시 searchHistoryQueries cache가 invalidate된다', async () => {
    server.use(
      http.get('*/api/v1/search/hybrid', () =>
        HttpResponse.json({
          results: [],
          total: 0,
          source_distribution: {},
          effective_tool_filters: null,
          effective_start_date: null,
          effective_end_date: null,
          is_tool_filter_inferred: false,
          is_date_filter_inferred: false,
        }),
      ),
    );
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const invalidateSpy = vi.spyOn(client, 'invalidateQueries');

    const { result } = renderHook(() => useHybridSearch({ keyword: 'foo', toolFilters: [], smartFilter: true }), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: searchHistoryQueries.all() });
  });

  it('keyword 빈 문자열이면 fetch 안 함 (enabled=false)', () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(() => useHybridSearch({ keyword: '', toolFilters: [], smartFilter: true }), {
      wrapper: makeWrapper(client),
    });
    expect(result.current.isFetching).toBe(false);
  });

  it('manual tool filter가 비어 있으면 tool_filters를 보내지 않고 smart_filter만 보낸다', async () => {
    const seenUrls: string[] = [];
    server.use(
      http.get('*/api/v1/search/hybrid', ({ request }) => {
        const url = new URL(request.url);
        seenUrls.push(url.toString());
        return HttpResponse.json({
          results: [],
          total: 0,
          source_distribution: {},
          effective_tool_filters: null,
          effective_start_date: null,
          effective_end_date: null,
          is_tool_filter_inferred: false,
          is_date_filter_inferred: false,
        });
      }),
    );
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });

    const { result } = renderHook(() => useHybridSearch({ keyword: 'foo', toolFilters: [], smartFilter: true }), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const url = new URL(seenUrls[0]!);
    expect(url.searchParams.get('smart_filter')).toBe('true');
    expect(url.searchParams.has('tool_filters')).toBe(false);
  });
});
