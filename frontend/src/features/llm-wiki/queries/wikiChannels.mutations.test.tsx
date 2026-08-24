import type { ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { wikiQueries } from './wiki.queries';
import {
  useCreateWikiFolderMutation,
  useDeleteWikiFolderMutation,
  useRenameWikiChannelMutation,
  useRenameWikiFolderMutation,
} from './wikiChannels.mutations';

const wikiApi = vi.hoisted(() => ({
  renameWikiChannel: vi.fn(),
  renameWikiFolder: vi.fn(),
  createWikiFolder: vi.fn(),
  deleteWikiFolder: vi.fn(),
}));
const toastMock = vi.hoisted(() => vi.fn());

// 실 요청과 sonner 렌더를 막는다 — 여기서 볼 것은 넘기는 인자와 무효화 대상뿐이다
vi.mock('../api/wikiRequests', () => wikiApi);
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
  wikiApi.renameWikiChannel.mockResolvedValue(undefined);
  wikiApi.renameWikiFolder.mockResolvedValue(undefined);
  wikiApi.createWikiFolder.mockResolvedValue(undefined);
  wikiApi.deleteWikiFolder.mockResolvedValue(undefined);
});

describe('useRenameWikiChannelMutation', () => {
  it('채널 id와 새 이름만 넘긴다', async () => {
    const { wrapper } = createHarness();
    const { result } = renderHook(() => useRenameWikiChannelMutation(), { wrapper });

    result.current.mutate({ channelId: 'ch-1', name: '결제' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(wikiApi.renameWikiChannel).toHaveBeenCalledWith('ch-1', '결제');
  });

  it('성공하면 채널 목록만 다시 읽는다 — 트리의 이름이 그 응답에서 온다', async () => {
    const { wrapper, invalidatedKeys } = createHarness();
    const { result } = renderHook(() => useRenameWikiChannelMutation(), { wrapper });

    result.current.mutate({ channelId: 'ch-1', name: '결제' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(invalidatedKeys()).toEqual([channelsKey]);
  });

  it('이름 중복 같은 실패는 서버 문구를 그대로 띄우고 캐시를 건드리지 않는다', async () => {
    wikiApi.renameWikiChannel.mockRejectedValue(apiError('DUPLICATE_NAME', '같은 이름의 채널이 있어요.'));
    const { wrapper, invalidatedKeys } = createHarness();
    const { result } = renderHook(() => useRenameWikiChannelMutation(), { wrapper });

    result.current.mutate({ channelId: 'ch-1', name: '결제' });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(toastMock).toHaveBeenCalledWith('같은 이름의 채널이 있어요.');
    expect(invalidatedKeys()).toEqual([]);
  });
});

describe('useRenameWikiFolderMutation', () => {
  it('폴더 이름 변경은 소속 채널 id를 함께 싣는다', async () => {
    const { wrapper } = createHarness();
    const { result } = renderHook(() => useRenameWikiFolderMutation(), { wrapper });

    result.current.mutate({ channelId: 'ch-1', folderId: 'fd-1', name: '장애 대응' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(wikiApi.renameWikiFolder).toHaveBeenCalledWith('ch-1', 'fd-1', '장애 대응');
  });

  it('폴더 이름도 채널 목록을 다시 읽는다 — 폴더 이름이 같은 응답에 실린다', async () => {
    const { wrapper, invalidatedKeys } = createHarness();
    const { result } = renderHook(() => useRenameWikiFolderMutation(), { wrapper });

    result.current.mutate({ channelId: 'ch-1', folderId: 'fd-1', name: '장애 대응' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(invalidatedKeys()).toEqual([channelsKey]);
  });

  it('실패하면 문구만 띄운다', async () => {
    wikiApi.renameWikiFolder.mockRejectedValue(apiError('FORBIDDEN', '채널 관리자만 바꿀 수 있어요.'));
    const { wrapper, invalidatedKeys } = createHarness();
    const { result } = renderHook(() => useRenameWikiFolderMutation(), { wrapper });

    result.current.mutate({ channelId: 'ch-1', folderId: 'fd-1', name: '장애 대응' });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(toastMock).toHaveBeenCalledWith('채널 관리자만 바꿀 수 있어요.');
    expect(invalidatedKeys()).toEqual([]);
  });
});

describe('useCreateWikiFolderMutation', () => {
  it('폴더 생성은 소속 채널 id와 이름만 넘긴다 — 폴더 안의 폴더 경로가 없다', async () => {
    const { wrapper } = createHarness();
    const { result } = renderHook(() => useCreateWikiFolderMutation(), { wrapper });

    result.current.mutate({ channelId: 'ch-1', name: '장애 대응' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(wikiApi.createWikiFolder).toHaveBeenCalledWith('ch-1', '장애 대응');
  });

  it('성공하면 채널 목록만 다시 읽는다 — 새 폴더가 그 응답에 실린다', async () => {
    const { wrapper, invalidatedKeys } = createHarness();
    const { result } = renderHook(() => useCreateWikiFolderMutation(), { wrapper });

    result.current.mutate({ channelId: 'ch-1', name: '장애 대응' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(invalidatedKeys()).toEqual([channelsKey]);
  });

  it('이름 중복 409는 서버 문구를 그대로 띄우고 캐시를 건드리지 않는다', async () => {
    wikiApi.createWikiFolder.mockRejectedValue(apiError('DUPLICATE_NAME', '같은 이름의 폴더가 있어요.'));
    const { wrapper, invalidatedKeys } = createHarness();
    const { result } = renderHook(() => useCreateWikiFolderMutation(), { wrapper });

    result.current.mutate({ channelId: 'ch-1', name: '장애 대응' });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(toastMock).toHaveBeenCalledWith('같은 이름의 폴더가 있어요.');
    expect(invalidatedKeys()).toEqual([]);
  });
});

describe('useDeleteWikiFolderMutation', () => {
  it('폴더 삭제는 소속 채널·폴더 id를 넘기고 성공하면 채널 목록만 다시 읽는다', async () => {
    const { wrapper, invalidatedKeys } = createHarness();
    const { result } = renderHook(() => useDeleteWikiFolderMutation(), { wrapper });

    result.current.mutate({ channelId: 'ch-1', folderId: 'fo-1' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(wikiApi.deleteWikiFolder).toHaveBeenCalledWith('ch-1', 'fo-1');
    // 폴더 안 문서는 서버가 채널 루트로 옮긴다 — 트리는 채널 응답 무효화만으로 따라온다
    expect(invalidatedKeys()).toEqual([channelsKey]);
  });

  it('실패는 서버 문구를 그대로 띄우고 캐시를 건드리지 않는다', async () => {
    wikiApi.deleteWikiFolder.mockRejectedValue(apiError('FORBIDDEN', '채널 관리자만 지울 수 있어요.'));
    const { wrapper, invalidatedKeys } = createHarness();
    const { result } = renderHook(() => useDeleteWikiFolderMutation(), { wrapper });

    result.current.mutate({ channelId: 'ch-1', folderId: 'fo-1' });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(toastMock).toHaveBeenCalledWith('채널 관리자만 지울 수 있어요.');
    expect(invalidatedKeys()).toEqual([]);
  });
});
