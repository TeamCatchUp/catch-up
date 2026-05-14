import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, fireEvent } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';

import { server } from '@/test/msw/server';

import ResultListSection from './ResultListSection';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => '/hybrid-search',
}));

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe('ResultListSection', () => {
  it('keyword 빈 문자열이면 Empty 표시 (fetch 없음)', () => {
    renderWithClient(
      <ResultListSection keyword="" tools={[]} page={1} onPageChange={() => {}} />,
    );
    expect(screen.getByText(/문서에서는 찾지 못했어요/)).toBeInTheDocument();
  });

  it('로딩 중에는 Loading 표시', () => {
    server.use(
      http.get('*/api/v1/search/hybrid', () => new Promise(() => {})), // pending
    );
    renderWithClient(
      <ResultListSection keyword="결제" tools={[]} page={1} onPageChange={() => {}} />,
    );
    expect(screen.getByText(/문서를 찾고 있어요/)).toBeInTheDocument();
  });

  it('results=[] 응답 시 Empty 표시', async () => {
    server.use(
      http.get('*/api/v1/search/hybrid', () =>
        HttpResponse.json({ results: [], total: 0, source_distribution: {} }),
      ),
    );
    renderWithClient(
      <ResultListSection keyword="결제" tools={[]} page={1} onPageChange={() => {}} />,
    );
    expect(await screen.findByText(/문서에서는 찾지 못했어요/)).toBeInTheDocument();
  });

  it('results 있을 때 카드 N개 + total>limit이면 Pagination 렌더', async () => {
    server.use(
      http.get('*/api/v1/search/hybrid', () =>
        HttpResponse.json({
          results: Array.from({ length: 7 }, (_, i) => ({
            id: String(i),
            source: 'jira',
            entity_type: 'issue',
            title: `이슈 ${i}`,
            text: '',
            author: 'a',
            updated_at: new Date().toISOString(),
            project_key: 'CU',
            issue_key: `CU-${i}`,
          })),
          total: 20,
          source_distribution: { jira: 20 },
        }),
      ),
    );
    renderWithClient(
      <ResultListSection keyword="결제" tools={[]} page={1} onPageChange={() => {}} />,
    );
    expect(await screen.findByText('이슈 0')).toBeInTheDocument();
    expect(screen.getByLabelText('이전 페이지')).toBeInTheDocument();
  });

  it('totalPages=1이면 Pagination 미렌더', async () => {
    server.use(
      http.get('*/api/v1/search/hybrid', () =>
        HttpResponse.json({
          results: [
            {
              id: '1',
              source: 'jira',
              entity_type: 'issue',
              title: '단일',
              text: '',
              author: 'a',
              updated_at: new Date().toISOString(),
              project_key: 'CU',
              issue_key: 'CU-1',
            },
          ],
          total: 1,
          source_distribution: { jira: 1 },
        }),
      ),
    );
    renderWithClient(
      <ResultListSection keyword="x" tools={[]} page={1} onPageChange={() => {}} />,
    );
    await screen.findByText('단일');
    expect(screen.queryByLabelText('이전 페이지')).not.toBeInTheDocument();
  });

  it('Pagination 클릭 시 onPageChange 호출', async () => {
    server.use(
      http.get('*/api/v1/search/hybrid', () =>
        HttpResponse.json({
          results: Array.from({ length: 7 }, (_, i) => ({
            id: String(i),
            source: 'jira',
            entity_type: 'issue',
            title: `이슈 ${i}`,
            text: '',
            author: 'a',
            updated_at: new Date().toISOString(),
            project_key: 'CU',
            issue_key: `CU-${i}`,
          })),
          total: 20,
          source_distribution: { jira: 20 },
        }),
      ),
    );
    const onPageChange = vi.fn();
    renderWithClient(
      <ResultListSection keyword="x" tools={[]} page={1} onPageChange={onPageChange} />,
    );
    await screen.findByText('이슈 0');
    fireEvent.click(screen.getByText('2'));
    expect(onPageChange).toHaveBeenCalledWith(2);
  });
});
