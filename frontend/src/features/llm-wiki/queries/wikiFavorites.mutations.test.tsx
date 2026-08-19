import type { ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { wikiQueries } from './wiki.queries';
import { useWikiFavoriteToggleMutation } from './wikiFavorites.mutations';

const apiMock = vi.hoisted(() => ({ put: vi.fn(), delete: vi.fn() }));
const toastMock = vi.hoisted(() => vi.fn());

// 실 요청과 sonner 렌더를 막는다 — 여기서 볼 것은 방향과 무효화 대상뿐이다
vi.mock('@/shared/api/client', () => ({ default: apiMock }));
vi.mock('@/shared/components/ui/toast', () => ({ toast: toastMock }));

const FAVORITE_URL = '/api/v1/wiki/favorites/af-1';

/** parseApiError가 읽는 최소 형태의 axios 에러 */
const apiError = (code: string, message: string) => ({
  isAxiosError: true,
  response: { data: { detail: { code, message } } },
});

const createHarness = () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const spy = vi.spyOn(client, 'invalidateQueries');

  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );

  return { wrapper, invalidatedKeys: () => spy.mock.calls.map(([filters]) => filters?.queryKey) };
};

beforeEach(() => {
  vi.clearAllMocks();
  apiMock.put.mockResolvedValue({ data: undefined });
  apiMock.delete.mockResolvedValue({ data: undefined });
});

describe('useWikiFavoriteToggleMutation', () => {
  it('등록은 PUT, 해제는 DELETE로 같은 자리를 뒤집는다', async () => {
    const { wrapper } = createHarness();
    const { result } = renderHook(() => useWikiFavoriteToggleMutation(), { wrapper });

    result.current.mutate({ artifactId: 'af-1', favorite: true });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiMock.put).toHaveBeenCalledWith(FAVORITE_URL);
    expect(apiMock.delete).not.toHaveBeenCalled();

    result.current.mutate({ artifactId: 'af-1', favorite: false });
    await waitFor(() => expect(apiMock.delete).toHaveBeenCalledWith(FAVORITE_URL));
    expect(apiMock.put).toHaveBeenCalledTimes(1);
  });

  it('성공하면 위키 뿌리를 무효화한다 — 즐겨찾기 섹션과 문서 행의 별이 함께 바뀐다', async () => {
    const { wrapper, invalidatedKeys } = createHarness();
    const { result } = renderHook(() => useWikiFavoriteToggleMutation(), { wrapper });

    result.current.mutate({ artifactId: 'af-1', favorite: true });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(invalidatedKeys()).toEqual([wikiQueries.all()]);
  });

  it('해제도 같은 뿌리를 무효화한다 — 방향에 따라 대상이 갈리지 않는다', async () => {
    const { wrapper, invalidatedKeys } = createHarness();
    const { result } = renderHook(() => useWikiFavoriteToggleMutation(), { wrapper });

    result.current.mutate({ artifactId: 'af-1', favorite: false });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(invalidatedKeys()).toEqual([wikiQueries.all()]);
  });

  it('실패하면 서버 문구만 띄우고 캐시를 건드리지 않는다', async () => {
    apiMock.put.mockRejectedValue(apiError('NOT_FOUND', '문서를 찾을 수 없어요.'));
    const { wrapper, invalidatedKeys } = createHarness();
    const { result } = renderHook(() => useWikiFavoriteToggleMutation(), { wrapper });

    result.current.mutate({ artifactId: 'af-1', favorite: true });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(toastMock).toHaveBeenCalledWith('문서를 찾을 수 없어요.');
    expect(invalidatedKeys()).toEqual([]);
  });
});
