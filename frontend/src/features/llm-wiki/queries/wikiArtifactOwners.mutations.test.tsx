import type { ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { knowledgeReviewQueries } from './knowledgeReview.queries';
import { wikiQueries } from './wiki.queries';
import {
  useAssignWikiArtifactOwnersMutation,
  useRemoveWikiArtifactOwnerMutation,
} from './wikiArtifactOwners.mutations';

const wikiApi = vi.hoisted(() => ({
  assignWikiArtifactOwner: vi.fn(),
  removeWikiArtifactOwner: vi.fn(),
}));
const toastMock = vi.hoisted(() => vi.fn());

// 실 요청과 sonner 렌더를 막는다 — 여기서 볼 것은 요청 모양과 무효화 대상뿐이다
vi.mock('../api/wikiRequests', () => wikiApi);
vi.mock('@/shared/components/ui/toast', () => ({ toast: toastMock }));

const ARTIFACT_ID = 'af-1';

/** 담당자 변경이 되돌려야 하는 캐시 세 갈래 — 큐 전체·문서 목록·그 문서의 발행판 */
const OWNER_CONSUMER_KEYS = [
  knowledgeReviewQueries.all(),
  [...wikiQueries.all(), 'artifacts'],
  wikiQueries.artifact(ARTIFACT_ID).queryKey,
];

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
  wikiApi.assignWikiArtifactOwner.mockResolvedValue({ artifact_id: ARTIFACT_ID, owners: [] });
  wikiApi.removeWikiArtifactOwner.mockResolvedValue(undefined);
});

describe('useAssignWikiArtifactOwnersMutation', () => {
  it('선택된 사람 수만큼 지정 요청을 보낸다', async () => {
    const { wrapper } = createHarness();
    const { result } = renderHook(() => useAssignWikiArtifactOwnersMutation(), { wrapper });

    result.current.mutate({ artifactId: ARTIFACT_ID, userIds: [7, 12] });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(wikiApi.assignWikiArtifactOwner).toHaveBeenCalledTimes(2);
    expect(wikiApi.assignWikiArtifactOwner).toHaveBeenCalledWith(ARTIFACT_ID, 7);
    expect(wikiApi.assignWikiArtifactOwner).toHaveBeenCalledWith(ARTIFACT_ID, 12);
  });

  it('성공하면 큐 전체·문서 목록·그 문서의 발행판을 되돌린다 — 담당자는 목록 행과 can_review에 함께 선다', async () => {
    const { wrapper, invalidatedKeys } = createHarness();
    const { result } = renderHook(() => useAssignWikiArtifactOwnersMutation(), { wrapper });

    result.current.mutate({ artifactId: ARTIFACT_ID, userIds: [7] });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(invalidatedKeys()).toEqual(OWNER_CONSUMER_KEYS);
  });

  it('자격이 없으면 서버 문구를 띄우고, 부분 성공이 남을 수 있어 캐시는 그래도 되돌린다', async () => {
    wikiApi.assignWikiArtifactOwner.mockRejectedValue(
      apiError('NOT_OWNER_MANAGER', '이 문서의 담당자를 지정할 자격이 없습니다.'),
    );
    const { wrapper, invalidatedKeys } = createHarness();
    const { result } = renderHook(() => useAssignWikiArtifactOwnersMutation(), { wrapper });

    result.current.mutate({ artifactId: ARTIFACT_ID, userIds: [7] });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(toastMock).toHaveBeenCalledWith('이 문서의 담당자를 지정할 자격이 없습니다.', {
      position: 'bottom-right',
    });
    expect(invalidatedKeys()).toEqual(OWNER_CONSUMER_KEYS);
  });
});

describe('useRemoveWikiArtifactOwnerMutation', () => {
  it('해제 대상 한 명을 그 문서 경로로 보내고 같은 캐시를 되돌린다', async () => {
    const { wrapper, invalidatedKeys } = createHarness();
    const { result } = renderHook(() => useRemoveWikiArtifactOwnerMutation(), { wrapper });

    result.current.mutate({ artifactId: ARTIFACT_ID, userId: 7 });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(wikiApi.removeWikiArtifactOwner).toHaveBeenCalledWith(ARTIFACT_ID, 7);
    expect(invalidatedKeys()).toEqual(OWNER_CONSUMER_KEYS);
  });

  it('관리자가 아니면 서버 문구만 띄우고 캐시를 건드리지 않는다 — 담당자 본인도 해제는 못 한다', async () => {
    wikiApi.removeWikiArtifactOwner.mockRejectedValue(
      apiError('NOT_OWNER_MANAGER', '이 문서의 담당자를 해제할 자격이 없습니다.'),
    );
    const { wrapper, invalidatedKeys } = createHarness();
    const { result } = renderHook(() => useRemoveWikiArtifactOwnerMutation(), { wrapper });

    result.current.mutate({ artifactId: ARTIFACT_ID, userId: 7 });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(toastMock).toHaveBeenCalledWith('이 문서의 담당자를 해제할 자격이 없습니다.', {
      position: 'bottom-right',
    });
    expect(invalidatedKeys()).toEqual([]);
  });
});
