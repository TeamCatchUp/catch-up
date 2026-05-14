import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';
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

// 50개까지 받을 수 있으나 페이지네이션 테스트는 11+개로 충분.
function makeMockResults(count: number, source = 'jira') {
  return Array.from({ length: count }, (_, i) => ({
    id: `${source}-${i}`,
    source,
    entity_type: 'issue',
    title: `이슈 ${i}`,
    text: '',
    author: 'a',
    updated_at: new Date().toISOString(),
    project_key: 'CU',
    issue_key: `CU-${i}`,
  }));
}

describe('ResultListSection', () => {
  it('keyword 빈 문자열이면 Empty 표시 (fetch 없음)', () => {
    renderWithClient(
      <ResultListSection keyword="" scope={[]} active="all" page={1} onPageChange={() => {}} />,
    );
    expect(screen.getByText(/문서에서는 찾지 못했어요/)).toBeInTheDocument();
  });

  it('로딩 중에는 Loading 표시', () => {
    server.use(http.get('*/api/v1/search/hybrid', () => new Promise(() => {})));
    renderWithClient(
      <ResultListSection keyword="결제" scope={[]} active="all" page={1} onPageChange={() => {}} />,
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
      <ResultListSection keyword="결제" scope={[]} active="all" page={1} onPageChange={() => {}} />,
    );
    expect(await screen.findByText(/문서에서는 찾지 못했어요/)).toBeInTheDocument();
  });

  it('10개 초과 결과 → Pagination 렌더, 1페이지엔 첫 10개만 표시', async () => {
    server.use(
      http.get('*/api/v1/search/hybrid', () =>
        HttpResponse.json({
          results: makeMockResults(15),
          total: 15,
          source_distribution: { jira: 15 },
        }),
      ),
    );
    renderWithClient(
      <ResultListSection keyword="결제" scope={[]} active="all" page={1} onPageChange={() => {}} />,
    );
    expect(await screen.findByText('이슈 0')).toBeInTheDocument();
    expect(screen.getByText('이슈 9')).toBeInTheDocument();
    // 1페이지엔 10번째 인덱스(11번째 카드) 없어야 함
    expect(screen.queryByText('이슈 10')).not.toBeInTheDocument();
    expect(screen.getByLabelText('이전 페이지')).toBeInTheDocument();
  });

  it('totalPages=1 (10개 이하)이면 Pagination 미렌더', async () => {
    server.use(
      http.get('*/api/v1/search/hybrid', () =>
        HttpResponse.json({
          results: makeMockResults(5),
          total: 5,
          source_distribution: { jira: 5 },
        }),
      ),
    );
    renderWithClient(
      <ResultListSection keyword="x" scope={[]} active="all" page={1} onPageChange={() => {}} />,
    );
    await screen.findByText('이슈 0');
    expect(screen.queryByLabelText('이전 페이지')).not.toBeInTheDocument();
  });

  it('scope 밖 active 클릭 시 EmptyState 표시 (client-side 분기)', async () => {
    server.use(
      http.get('*/api/v1/search/hybrid', () =>
        HttpResponse.json({
          results: makeMockResults(5),
          total: 5,
          source_distribution: { jira: 5 },
        }),
      ),
    );
    renderWithClient(
      <ResultListSection
        keyword="foo"
        scope={['jira', 'slack']}
        active="confluence"
        page={1}
        onPageChange={() => {}}
      />,
    );
    expect(await screen.findByText(/문서에서는 찾지 못했어요/)).toBeInTheDocument();
  });

  it('active=jira일 때 jira만 client-side filter', async () => {
    server.use(
      http.get('*/api/v1/search/hybrid', () =>
        HttpResponse.json({
          results: [
            ...makeMockResults(3, 'jira'),
            ...makeMockResults(2, 'slack').map((r) => ({ ...r, title: `슬랙 ${r.id}` })),
          ],
          total: 5,
          source_distribution: { jira: 3, slack: 2 },
        }),
      ),
    );
    renderWithClient(
      <ResultListSection
        keyword="x"
        scope={['jira', 'slack']}
        active="jira"
        page={1}
        onPageChange={() => {}}
      />,
    );
    await screen.findByText('이슈 0');
    expect(screen.getByText('이슈 1')).toBeInTheDocument();
    expect(screen.getByText('이슈 2')).toBeInTheDocument();
    // slack 결과는 미표시
    expect(screen.queryByText(/슬랙/)).not.toBeInTheDocument();
  });

  it('Pagination 클릭 시 onPageChange 호출', async () => {
    server.use(
      http.get('*/api/v1/search/hybrid', () =>
        HttpResponse.json({
          results: makeMockResults(15),
          total: 15,
          source_distribution: { jira: 15 },
        }),
      ),
    );
    const onPageChange = vi.fn();
    renderWithClient(
      <ResultListSection keyword="x" scope={[]} active="all" page={1} onPageChange={onPageChange} />,
    );
    await screen.findByText('이슈 0');
    fireEvent.click(screen.getByText('2'));
    expect(onPageChange).toHaveBeenCalledWith(2);
  });
});
