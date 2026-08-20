import type { PropsWithChildren } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';

import { server } from '@/test/msw/server';

import { useWikiDashboardModel } from './useWikiDashboardModel';

function makeWrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });

  return function Wrapper({ children }: PropsWithChildren) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

/** 목록 요청 URL을 모아 준다 — 훅이 낸 limit·offset을 그대로 볼 수 있다. */
function stubWikiEndpoints() {
  const artifactUrls: string[] = [];

  server.use(
    http.get('*/api/v1/wiki/artifacts', ({ request }) => {
      artifactUrls.push(request.url);
      return HttpResponse.json({ items: [], total: 0 });
    }),
    http.get('*/api/v1/wiki/channels', () => HttpResponse.json({ channels: [] })),
    http.get('*/api/v1/wiki/members', () => HttpResponse.json({ items: [] })),
    http.get('*/api/v1/auth/me', () => HttpResponse.json({ user_id: 1 })),
  );

  return artifactUrls;
}

describe('useWikiDashboardModel', () => {
  it('쪽 크기가 바뀌면 1쪽으로 돌아간다', async () => {
    stubWikiEndpoints();
    const { result, rerender } = renderHook(({ pageSize }) => useWikiDashboardModel(pageSize), {
      initialProps: { pageSize: 20 },
      wrapper: makeWrapper(),
    });

    act(() => result.current.onQueryStateChange({ ...result.current.queryState, page: 3 }));
    expect(result.current.queryState.page).toBe(3);

    rerender({ pageSize: 50 });
    expect(result.current.queryState.page).toBe(1);
  });

  it('쪽 크기가 그대로면 쪽을 건드리지 않는다', () => {
    stubWikiEndpoints();
    const { result, rerender } = renderHook(({ pageSize }) => useWikiDashboardModel(pageSize), {
      initialProps: { pageSize: 20 },
      wrapper: makeWrapper(),
    });

    act(() => result.current.onQueryStateChange({ ...result.current.queryState, page: 3 }));
    rerender({ pageSize: 20 });

    expect(result.current.queryState.page).toBe(3);
  });

  it('바뀐 쪽 크기로는 offset 0인 요청만 나간다', async () => {
    const artifactUrls = stubWikiEndpoints();
    const { result, rerender } = renderHook(({ pageSize }) => useWikiDashboardModel(pageSize), {
      initialProps: { pageSize: 20 },
      wrapper: makeWrapper(),
    });

    act(() => result.current.onQueryStateChange({ ...result.current.queryState, page: 3 }));
    await waitFor(() => expect(artifactUrls.some((url) => url.includes('offset=40'))).toBe(true));

    rerender({ pageSize: 50 });

    // limit=50이 실린 요청은 전부 첫 쪽이어야 한다 — 이전 쪽 번호가 남으면 빈 쪽을 부른다.
    await waitFor(() => expect(artifactUrls.some((url) => url.includes('limit=50'))).toBe(true));
    const resized = artifactUrls.filter((url) => url.includes('limit=50'));
    expect(resized.every((url) => url.includes('offset=0'))).toBe(true);
  });
});
