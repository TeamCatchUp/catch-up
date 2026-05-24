import type { ReactNode } from 'react';
import { QueryClient, QueryClientProvider, useMutation } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';

import { server } from '@/test/msw/server';

import { originalFileUrlMutations } from './originalFileUrl.mutations';

function createWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

describe('originalFileUrlMutations.download', () => {
  it('mutationKey 가 안정적이다', () => {
    expect(originalFileUrlMutations.download().mutationKey).toEqual([
      'search',
      'original',
      'file-url',
      'download',
    ]);
  });

  it('POST 요청을 보내고 응답을 그대로 반환한다', async () => {
    server.use(
      http.post('/api/v1/search/original/file-url', async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        expect(body).toEqual({
          connector: 'channel_talk',
          document_id: 'channel_talk:user_chat:1',
          file_key: 'file-abc',
        });
        return HttpResponse.json({
          connector: 'channel_talk',
          entity_type: 'user_chat',
          document_id: 'channel_talk:user_chat:1',
          file_key: 'file-abc',
          url: 'https://channel.io/presigned/...',
          expires_in_seconds: 900,
          fetched_at: '2026-05-24T00:00:00Z',
        });
      }),
    );

    const { result } = renderHook(() => useMutation(originalFileUrlMutations.download()), {
      wrapper: createWrapper(),
    });

    result.current.mutate({
      connector: 'channel_talk',
      document_id: 'channel_talk:user_chat:1',
      file_key: 'file-abc',
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.data.url).toBe('https://channel.io/presigned/...');
  });

  it('400 에러 시 isError 가 true 가 된다', async () => {
    server.use(
      http.post('/api/v1/search/original/file-url', () =>
        HttpResponse.json({ detail: 'invalid file_key' }, { status: 400 }),
      ),
    );

    const { result } = renderHook(() => useMutation(originalFileUrlMutations.download()), {
      wrapper: createWrapper(),
    });

    result.current.mutate({
      connector: 'channel_talk',
      document_id: 'channel_talk:user_chat:1',
      file_key: '',
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
