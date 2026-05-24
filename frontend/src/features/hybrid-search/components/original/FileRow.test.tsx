import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import type { ReactNode } from 'react';
import { toast } from 'sonner';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { OriginalFile } from '@/features/hybrid-search/types/originalApi';
import { server } from '@/test/msw/server';

import FileRow from './FileRow';

const baseFile: OriginalFile = {
  file_key: 'file-abc',
  name: '결제내역서.pdf',
  content_type: 'application/pdf',
  size: 248_120,
};

interface RenderProps {
  file?: OriginalFile;
  connector?: 'channel_talk';
  documentId?: string;
}

function renderFileRow(props?: RenderProps) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  }
  return render(
    <Wrapper>
      <FileRow
        file={props?.file ?? baseFile}
        connector={props?.connector ?? 'channel_talk'}
        documentId={props?.documentId ?? 'channel_talk:user_chat:1'}
      />
    </Wrapper>,
  );
}

describe('FileRow', () => {
  let openSpy: ReturnType<typeof vi.spyOn>;
  let closeSpy: ReturnType<typeof vi.fn>;
  let fakeWindow: { location: { href: string }; close: ReturnType<typeof vi.fn> };

  beforeEach(() => {
    closeSpy = vi.fn();
    fakeWindow = { location: { href: '' }, close: closeSpy };
    openSpy = vi.spyOn(window, 'open').mockReturnValue(fakeWindow as unknown as Window);
    vi.spyOn(toast, 'error').mockImplementation(() => 'mock-id');
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('file_key 있는 파일은 button 으로 렌더되고 파일명·크기 표시', () => {
    renderFileRow();
    expect(screen.getByRole('button', { name: /결제내역서\.pdf/ })).toBeInTheDocument();
    expect(screen.getByText(/242\.3KB/)).toBeInTheDocument();
  });

  it('file_key 없는 파일은 비링크 div 유지 (button 없음)', () => {
    renderFileRow({ file: { ...baseFile, file_key: undefined } });
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
    expect(screen.getByText('결제내역서.pdf')).toBeInTheDocument();
  });

  it('클릭 시 window.open 동기 호출 + 성공 시 새 탭 location 갱신', async () => {
    server.use(
      http.post('/api/v1/search/original/file-url', () =>
        HttpResponse.json({
          connector: 'channel_talk',
          entity_type: 'user_chat',
          document_id: 'channel_talk:user_chat:1',
          file_key: 'file-abc',
          url: 'https://channel.io/presigned/abc',
          expires_in_seconds: 900,
          fetched_at: '2026-05-24T00:00:00Z',
        }),
      ),
    );

    renderFileRow();
    const user = userEvent.setup();
    await user.click(screen.getByRole('button'));

    expect(openSpy).toHaveBeenCalledWith('about:blank', '_blank');
    await vi.waitFor(() =>
      expect(fakeWindow.location.href).toBe('https://channel.io/presigned/abc'),
    );
  });

  it('에러 시 빈 탭 close + toast.error 호출', async () => {
    server.use(
      http.post('/api/v1/search/original/file-url', () =>
        HttpResponse.json({ detail: 'file_key not found' }, { status: 404 }),
      ),
    );

    renderFileRow();
    const user = userEvent.setup();
    await user.click(screen.getByRole('button'));

    await vi.waitFor(() => {
      expect(closeSpy).toHaveBeenCalled();
      expect(toast.error).toHaveBeenCalledWith('file_key not found');
    });
  });

  it('빈 url 응답 시 빈 탭 close + 안내 toast', async () => {
    server.use(
      http.post('/api/v1/search/original/file-url', () =>
        HttpResponse.json({
          connector: 'channel_talk',
          entity_type: 'user_chat',
          document_id: 'channel_talk:user_chat:1',
          file_key: 'file-abc',
          url: '',
          expires_in_seconds: 900,
          fetched_at: '2026-05-24T00:00:00Z',
        }),
      ),
    );

    renderFileRow();
    const user = userEvent.setup();
    await user.click(screen.getByRole('button'));

    await vi.waitFor(() => {
      expect(closeSpy).toHaveBeenCalled();
      expect(toast.error).toHaveBeenCalledWith('파일을 불러올 수 없습니다');
    });
  });
});
