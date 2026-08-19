import type { ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { wikiQueries } from './wiki.queries';
import {
  useCreateWikiFolderMutation,
  useRenameWikiChannelMutation,
  useRenameWikiFolderMutation,
} from './wikiChannels.mutations';

const apiMock = vi.hoisted(() => ({ patch: vi.fn(), post: vi.fn() }));
const toastMock = vi.hoisted(() => vi.fn());

// 실 요청과 sonner 렌더를 막는다 — 여기서 볼 것은 경로와 무효화 대상뿐이다
vi.mock('@/shared/api/client', () => ({ default: apiMock }));
vi.mock('@/shared/components/ui/toast', () => ({ toast: toastMock }));

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

const channelsKey = wikiQueries.channels().queryKey;

beforeEach(() => {
  vi.clearAllMocks();
  apiMock.patch.mockResolvedValue({ data: undefined });
  apiMock.post.mockResolvedValue({ data: undefined });
});

describe('useRenameWikiChannelMutation', () => {
  it('채널 경로로 이름만 보낸다', async () => {
    const { wrapper } = createHarness();
    const { result } = renderHook(() => useRenameWikiChannelMutation(), { wrapper });

    result.current.mutate({ channelId: 'ch-1', name: '결제' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiMock.patch).toHaveBeenCalledWith('/api/v1/wiki/channels/ch-1', { name: '결제' });
  });

  it('성공하면 채널 목록만 다시 읽는다 — 트리의 이름이 그 응답에서 온다', async () => {
    const { wrapper, invalidatedKeys } = createHarness();
    const { result } = renderHook(() => useRenameWikiChannelMutation(), { wrapper });

    result.current.mutate({ channelId: 'ch-1', name: '결제' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(invalidatedKeys()).toEqual([channelsKey]);
  });

  it('이름 중복 같은 실패는 서버 문구를 그대로 띄우고 캐시를 건드리지 않는다', async () => {
    apiMock.patch.mockRejectedValue(apiError('DUPLICATE_NAME', '같은 이름의 채널이 있어요.'));
    const { wrapper, invalidatedKeys } = createHarness();
    const { result } = renderHook(() => useRenameWikiChannelMutation(), { wrapper });

    result.current.mutate({ channelId: 'ch-1', name: '결제' });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(toastMock).toHaveBeenCalledWith('같은 이름의 채널이 있어요.');
    expect(invalidatedKeys()).toEqual([]);
  });
});

describe('useRenameWikiFolderMutation', () => {
  it('폴더 경로는 소속 채널 id를 함께 싣는다', async () => {
    const { wrapper } = createHarness();
    const { result } = renderHook(() => useRenameWikiFolderMutation(), { wrapper });

    result.current.mutate({ channelId: 'ch-1', folderId: 'fd-1', name: '장애 대응' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiMock.patch).toHaveBeenCalledWith('/api/v1/wiki/channels/ch-1/folders/fd-1', { name: '장애 대응' });
  });

  it('폴더 이름도 채널 목록을 다시 읽는다 — 폴더 이름이 같은 응답에 실린다', async () => {
    const { wrapper, invalidatedKeys } = createHarness();
    const { result } = renderHook(() => useRenameWikiFolderMutation(), { wrapper });

    result.current.mutate({ channelId: 'ch-1', folderId: 'fd-1', name: '장애 대응' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(invalidatedKeys()).toEqual([channelsKey]);
  });

  it('실패하면 문구만 띄운다', async () => {
    apiMock.patch.mockRejectedValue(apiError('FORBIDDEN', '채널 관리자만 바꿀 수 있어요.'));
    const { wrapper, invalidatedKeys } = createHarness();
    const { result } = renderHook(() => useRenameWikiFolderMutation(), { wrapper });

    result.current.mutate({ channelId: 'ch-1', folderId: 'fd-1', name: '장애 대응' });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(toastMock).toHaveBeenCalledWith('채널 관리자만 바꿀 수 있어요.');
    expect(invalidatedKeys()).toEqual([]);
  });
});

describe('useCreateWikiFolderMutation', () => {
  it('채널 폴더 경로로 이름만 보낸다 — 폴더 안의 폴더 경로가 없다', async () => {
    const { wrapper } = createHarness();
    const { result } = renderHook(() => useCreateWikiFolderMutation(), { wrapper });

    result.current.mutate({ channelId: 'ch-1', name: '장애 대응' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiMock.post).toHaveBeenCalledWith('/api/v1/wiki/channels/ch-1/folders', { name: '장애 대응' });
  });

  it('성공하면 채널 목록만 다시 읽는다 — 새 폴더가 그 응답에 실린다', async () => {
    const { wrapper, invalidatedKeys } = createHarness();
    const { result } = renderHook(() => useCreateWikiFolderMutation(), { wrapper });

    result.current.mutate({ channelId: 'ch-1', name: '장애 대응' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(invalidatedKeys()).toEqual([channelsKey]);
  });

  it('이름 중복 409는 서버 문구를 그대로 띄우고 캐시를 건드리지 않는다', async () => {
    apiMock.post.mockRejectedValue(apiError('DUPLICATE_NAME', '같은 이름의 폴더가 있어요.'));
    const { wrapper, invalidatedKeys } = createHarness();
    const { result } = renderHook(() => useCreateWikiFolderMutation(), { wrapper });

    result.current.mutate({ channelId: 'ch-1', name: '장애 대응' });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(toastMock).toHaveBeenCalledWith('같은 이름의 폴더가 있어요.');
    expect(invalidatedKeys()).toEqual([]);
  });
});
