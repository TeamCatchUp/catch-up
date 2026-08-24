import type { ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { wikiQueries } from './wiki.queries';
import { useMoveWikiArtifactMutation } from './wikiArtifacts.mutations';

const wikiApi = vi.hoisted(() => ({ moveWikiArtifact: vi.fn() }));
const toastMock = vi.hoisted(() => vi.fn());

// 실 요청과 sonner 렌더를 막는다 — 여기서 볼 것은 방향과 무효화 대상뿐이다
vi.mock('../api/wikiRequests', () => wikiApi);
vi.mock('@/shared/components/ui/toast', () => ({ toast: toastMock }));

const ARTIFACT_ID = 'af-1';

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
  wikiApi.moveWikiArtifact.mockResolvedValue(undefined);
});

describe('useMoveWikiArtifactMutation', () => {
  it('고른 폴더 id를 그 문서 경로로 보낸다', async () => {
    const { wrapper } = createHarness();
    const { result } = renderHook(() => useMoveWikiArtifactMutation(), { wrapper });

    result.current.mutate({ artifactId: ARTIFACT_ID, folderId: 'fd-9' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(wikiApi.moveWikiArtifact).toHaveBeenCalledWith(ARTIFACT_ID, 'fd-9');
  });

  it('채널 바로 아래로 옮기면 folder_id 자리에 null이 나간다', async () => {
    const { wrapper } = createHarness();
    const { result } = renderHook(() => useMoveWikiArtifactMutation(), { wrapper });

    result.current.mutate({ artifactId: ARTIFACT_ID, folderId: null });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(wikiApi.moveWikiArtifact).toHaveBeenCalledWith(ARTIFACT_ID, null);
  });

  it('성공하면 위키 뿌리를 무효화한다 — 채널 트리와 문서 목록이 함께 바뀐다', async () => {
    const { wrapper, invalidatedKeys } = createHarness();
    const { result } = renderHook(() => useMoveWikiArtifactMutation(), { wrapper });

    result.current.mutate({ artifactId: ARTIFACT_ID, folderId: 'fd-9' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(invalidatedKeys()).toEqual([wikiQueries.all()]);
  });

  it('검수 자격이 없으면 서버 문구만 띄우고 캐시를 건드리지 않는다', async () => {
    wikiApi.moveWikiArtifact.mockRejectedValue(apiError('NOT_DOCUMENT_REVIEWER', '이 문서를 옮길 권한이 없습니다.'));
    const { wrapper, invalidatedKeys } = createHarness();
    const { result } = renderHook(() => useMoveWikiArtifactMutation(), { wrapper });

    result.current.mutate({ artifactId: ARTIFACT_ID, folderId: 'fd-9' });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(toastMock).toHaveBeenCalledWith('이 문서를 옮길 권한이 없습니다.');
    expect(invalidatedKeys()).toEqual([]);
  });
});
