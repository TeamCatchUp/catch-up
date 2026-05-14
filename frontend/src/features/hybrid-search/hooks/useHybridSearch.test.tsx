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
        HttpResponse.json({ results: [], total: 0, source_distribution: {} }),
      ),
    );
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const invalidateSpy = vi.spyOn(client, 'invalidateQueries');

    const { result } = renderHook(
      () => useHybridSearch({ keyword: 'foo', tools: [], page: 1 }),
      { wrapper: makeWrapper(client) },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: searchHistoryQueries.all() });
  });

  it('keyword 빈 문자열이면 fetch 안 함 (enabled=false)', () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(
      () => useHybridSearch({ keyword: '', tools: [], page: 1 }),
      { wrapper: makeWrapper(client) },
    );
    expect(result.current.isFetching).toBe(false);
  });
});
