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
    tools: [],
    draftKeyword: '결제',
    onDraftKeywordChange: () => {},
    onSubmit: () => {},
    onClear: () => {},
    activeTab: 'all' as const,
    onTabChange: () => {},
  };
}

describe('ResultPageHeader', () => {
  it('AccentTabs를 렌더 (전체/Confluence/Jira/Slack/Github/채널톡)', async () => {
    server.use(
      http.get('*/api/v1/search/hybrid', () =>
        HttpResponse.json({ results: [], total: 0, source_distribution: {} }),
      ),
    );
    renderWithClient(<ResultPageHeader {...makeDefaultProps()} />);
    expect(screen.getByText('전체')).toBeInTheDocument();
    expect(screen.getByText('Jira')).toBeInTheDocument();
    expect(screen.getByText('Slack')).toBeInTheDocument();
    expect(screen.getByText('Confluence')).toBeInTheDocument();
    expect(screen.getByText('Github')).toBeInTheDocument();
    expect(screen.getByText('채널톡')).toBeInTheDocument();
  });

  it('distribution 응답 후 각 탭의 count 표시', async () => {
    server.use(
      http.get('*/api/v1/search/hybrid', () =>
        HttpResponse.json({
          results: [],
          total: 0,
          source_distribution: { jira: 5, slack: 3, github: 2 },
        }),
      ),
    );
    renderWithClient(<ResultPageHeader {...makeDefaultProps()} />);

    await waitFor(() => {
      const badges = screen
        .getAllByText(/^\d+$/)
        .filter((el) => el.hasAttribute('data-tab-state-badge'));
      const counts = badges.map((b) => b.textContent);
      expect(counts).toContain('5');
      expect(counts).toContain('3');
      expect(counts).toContain('2');
    });
  });

  it('Jira 탭 클릭 시 onTabChange("jira") 호출', async () => {
    server.use(
      http.get('*/api/v1/search/hybrid', () =>
        HttpResponse.json({ results: [], total: 0, source_distribution: { jira: 5 } }),
      ),
    );
    const onTabChange = vi.fn();
    const user = userEvent.setup();
    renderWithClient(<ResultPageHeader {...makeDefaultProps()} onTabChange={onTabChange} />);

    await user.click(screen.getByRole('tab', { name: /Jira/ }));
    expect(onTabChange).toHaveBeenCalledWith('jira');
  });
});
