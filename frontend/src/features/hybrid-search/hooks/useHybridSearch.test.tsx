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
      () => useHybridSearch({ keyword: 'foo', scope: [], active: 'all', page: 1 }),
      { wrapper: makeWrapper(client) },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: searchHistoryQueries.all() });
  });

  it('keyword 빈 문자열이면 fetch 안 함 (enabled=false)', () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(
      () => useHybridSearch({ keyword: '', scope: [], active: 'all', page: 1 }),
      { wrapper: makeWrapper(client) },
    );
    expect(result.current.isFetching).toBe(false);
  });

  it('active가 scope 밖이면 isOutOfScope=true + fetch 안 함', () => {
    let fetchCalled = false;
    server.use(
      http.get('*/api/v1/search/hybrid', () => {
        fetchCalled = true;
        return HttpResponse.json({ results: [], total: 0, source_distribution: {} });
      }),
    );
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(
      () => useHybridSearch({ keyword: 'foo', scope: ['jira', 'slack'], active: 'confluence', page: 1 }),
      { wrapper: makeWrapper(client) },
    );
    expect(result.current.isOutOfScope).toBe(true);
    expect(result.current.isFetching).toBe(false);
    expect(fetchCalled).toBe(false);
  });

  it('active=all 이면 scope와 무관하게 isOutOfScope=false', () => {
    server.use(
      http.get('*/api/v1/search/hybrid', () =>
        HttpResponse.json({ results: [], total: 0, source_distribution: {} }),
      ),
    );
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(
      () => useHybridSearch({ keyword: 'foo', scope: ['jira', 'slack'], active: 'all', page: 1 }),
      { wrapper: makeWrapper(client) },
    );
    expect(result.current.isOutOfScope).toBe(false);
  });

  it('scope가 비어있으면 active 무관하게 isOutOfScope=false', () => {
    server.use(
      http.get('*/api/v1/search/hybrid', () =>
        HttpResponse.json({ results: [], total: 0, source_distribution: {} }),
      ),
    );
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(
      () => useHybridSearch({ keyword: 'foo', scope: [], active: 'jira', page: 1 }),
      { wrapper: makeWrapper(client) },
    );
    expect(result.current.isOutOfScope).toBe(false);
  });
});
