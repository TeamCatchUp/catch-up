import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';

import { server } from '@/test/msw/server';

import ResultPageHeader from './ResultPageHeader';

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => '/hybrid-search',
}));

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

function makeDefaultProps() {
  return {
    keyword: '결제',
    toolFilters: [],
    draftKeyword: '결제',
    onDraftKeywordChange: () => {},
    draftChips: [],
    onDraftChipsChange: () => {},
    dateRange: undefined,
    draftDateRange: undefined,
    onDraftDateRangeChange: () => {},
    smartFilter: true,
    draftSmartFilter: true,
    onDraftSmartFilterChange: () => {},
    onSubmit: () => {},
    onHistorySubmit: () => {},
    onClear: () => {},
    onAiModeClick: () => {},
    activeTab: 'all' as const,
    onTabChange: () => {},
    sortOrder: 'newest' as const,
    onSortChange: () => {},
  };
}

describe('ResultPageHeader', () => {
  it('로딩 중에는 모든 source 탭을 count badge 없이 표시', () => {
    server.use(http.get('*/api/v1/search/hybrid', () => new Promise(() => {})));
    const { container } = renderWithClient(<ResultPageHeader {...makeDefaultProps()} />);
    expect(screen.getByText('전체')).toBeInTheDocument();
    expect(screen.getByText('Jira')).toBeInTheDocument();
    expect(screen.getByText('Slack')).toBeInTheDocument();
    expect(screen.getByText('Confluence')).toBeInTheDocument();
    expect(screen.getByText('Github')).toBeInTheDocument();
    expect(screen.getByText('채널톡')).toBeInTheDocument();
    // count badge 미렌더 — data-tab-state-badge 속성을 가진 요소 없어야 함.
    expect(container.querySelectorAll('[data-tab-state-badge]')).toHaveLength(0);
  });

  it('데이터 도착 후 results=[]면 source 탭은 모두 숨김, 전체 탭만 표시', async () => {
    server.use(
      http.get('*/api/v1/search/hybrid', () => HttpResponse.json({ results: [], total: 0, source_distribution: {} })),
    );
    const { container } = renderWithClient(<ResultPageHeader {...makeDefaultProps()} />);
    expect(screen.getByText('전체')).toBeInTheDocument();
    await waitFor(() => {
      const badges = Array.from(container.querySelectorAll('[data-tab-state-badge]'));
      expect(badges.map((b) => b.textContent)).toEqual(['0']);
      expect(screen.queryByText('Jira')).not.toBeInTheDocument();
      expect(screen.queryByText('Slack')).not.toBeInTheDocument();
      expect(screen.queryByText('Confluence')).not.toBeInTheDocument();
      expect(screen.queryByText('Github')).not.toBeInTheDocument();
      expect(screen.queryByText('채널톡')).not.toBeInTheDocument();
    });
  });

  it('list 응답의 results에서 source별 count를 client-side 계산하여 탭 배지 표시', async () => {
    // distribution은 results 배열에서 계산. source_distribution 필드는 더 이상 사용 안 함.
    const results = [
      ...Array.from({ length: 5 }, (_, i) => ({
        id: `jira-${i}`,
        source: 'jira',
        entity_type: 'issue',
        title: `j${i}`,
        text: '',
      })),
      ...Array.from({ length: 3 }, (_, i) => ({
        id: `slack-${i}`,
        source: 'slack',
        entity_type: 'message',
        title: `s${i}`,
        text: '',
      })),
      ...Array.from({ length: 2 }, (_, i) => ({
        id: `github-${i}`,
        source: 'github',
        entity_type: 'pr',
        title: `g${i}`,
        text: '',
      })),
    ];
    server.use(
      http.get('*/api/v1/search/hybrid', () =>
        HttpResponse.json({ results, total: results.length, source_distribution: {} }),
      ),
    );
    const { container } = renderWithClient(<ResultPageHeader {...makeDefaultProps()} />);

    await waitFor(() => {
      const badges = Array.from(container.querySelectorAll('[data-tab-state-badge]'));
      const counts = badges.map((b) => b.textContent);
      expect(counts).toEqual(['10', '5', '3', '2']);
    });
  });

  it('Jira 탭 클릭 시 onTabChange("jira") 호출', async () => {
    const results = Array.from({ length: 5 }, (_, i) => ({
      id: `jira-${i}`,
      source: 'jira',
      entity_type: 'issue',
      title: `j${i}`,
      text: '',
    }));
    server.use(
      http.get('*/api/v1/search/hybrid', () =>
        HttpResponse.json({ results, total: results.length, source_distribution: {} }),
      ),
    );
    const onTabChange = vi.fn();
    const user = userEvent.setup();
    renderWithClient(<ResultPageHeader {...makeDefaultProps()} onTabChange={onTabChange} />);

    await user.click(await screen.findByRole('tab', { name: /Jira/ }));
    expect(onTabChange).toHaveBeenCalledWith('jira');
  });

  it('uses the same max content width as the result body', () => {
    const { container } = renderWithClient(<ResultPageHeader {...makeDefaultProps()} />);

    const innerShell = container.querySelector('header > div');
    expect(innerShell).toHaveClass('max-w-355');
  });
});
