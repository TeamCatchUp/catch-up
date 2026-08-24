import type { PropsWithChildren } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse, type HttpResponseResolver } from 'msw';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { toast } from '@/shared/components/ui/toast';
import { server } from '@/test/msw/server';

import { useWikiDocumentModel } from './useWikiDocumentModel';

vi.mock('@/shared/components/ui/toast', () => ({ toast: vi.fn() }));

const toastMock = vi.mocked(toast);

const CHANNELS = {
  channels: [
    {
      id: 'ch-1',
      name: '결제',
      workspace_id: 1,
      is_admin: false,
      document_count: 1,
      folders: [],
      purpose_presets: [],
      definitions: [],
    },
  ],
};

const DOCUMENT = {
  artifact_id: 'art-1',
  channel_id: 'ch-1',
  definition_id: null,
  kind: 'guide',
  title: '결제 실패 대응 가이드',
  folder_id: null,
  owners: [],
  is_favorite: false,
  revision_id: 'rev-1',
  published_at: '2026-08-23T00:00:00Z',
  last_edited_by: null,
  last_edited_at: null,
  blocks: [],
};

function makeWrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });

  return function Wrapper({ children }: PropsWithChildren) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

/** 문서 상세 응답만 갈아 끼운다 — 채널 목록은 늘 성공한다 */
function stubDocumentEndpoint(respond: HttpResponseResolver) {
  server.use(
    http.get('*/api/v1/wiki/artifacts/:artifactId', respond),
    http.get('*/api/v1/wiki/channels', () => HttpResponse.json(CHANNELS)),
  );
}

/** 정형 에러 응답({ detail: { code, message } }) */
const apiError = (code: string, message: string, status: number) =>
  HttpResponse.json({ detail: { code, message } }, { status });

beforeEach(() => {
  toastMock.mockClear();
});

describe('useWikiDocumentModel', () => {
  it('미발행 404는 조회 실패가 아니라 notPublished로 선다', async () => {
    stubDocumentEndpoint(() => apiError('ARTIFACT_NOT_PUBLISHED', '발행된 판이 없습니다.', 404));
    const { result } = renderHook(() => useWikiDocumentModel('art-1'), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.notPublished).toBe(true));
    expect(result.current.isPending).toBe(false);
    expect(result.current.document).toBeNull();
    expect(result.current.breadcrumbs).toEqual([]);
  });

  it('미발행 404는 실패 토스트를 띄우지 않는다 — 안내 화면이 대신 선다', async () => {
    stubDocumentEndpoint(() => apiError('ARTIFACT_NOT_PUBLISHED', '발행된 판이 없습니다.', 404));
    const { result } = renderHook(() => useWikiDocumentModel('art-1'), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.notPublished).toBe(true));
    expect(toastMock).not.toHaveBeenCalled();
  });

  it('미발행이 아닌 실패는 그대로 토스트로 흐른다', async () => {
    stubDocumentEndpoint(() => apiError('WIKI_ARTIFACT_READ_FAILED', '문서를 읽지 못했습니다.', 500));
    const { result } = renderHook(() => useWikiDocumentModel('art-1'), { wrapper: makeWrapper() });

    await waitFor(() => expect(toastMock).toHaveBeenCalledTimes(1));
    expect(toastMock.mock.calls[0][0]).toBe('문서를 읽지 못했습니다.');
    expect(result.current.notPublished).toBe(false);
    expect(result.current.document).toBeNull();
  });

  it('발행판이 오면 문서와 경로가 함께 선다', async () => {
    stubDocumentEndpoint(() => HttpResponse.json(DOCUMENT));
    const { result } = renderHook(() => useWikiDocumentModel('art-1'), { wrapper: makeWrapper() });

    await waitFor(() => expect(result.current.document).not.toBeNull());
    expect(result.current.notPublished).toBe(false);
    expect(result.current.breadcrumbs).toEqual([
      { kind: 'channel', label: '결제', id: 'ch-1' },
      { kind: 'document', label: '결제 실패 대응 가이드' },
    ]);
    expect(toastMock).not.toHaveBeenCalled();
  });
});
