import type { ComponentProps, ReactElement } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render } from '@testing-library/react';

import ResultListSection from './ResultListSection';

type ResultListSectionProps = ComponentProps<typeof ResultListSection>;

function renderWithClient(ui: ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

export function renderResultListSection(overrides: Partial<ResultListSectionProps> = {}) {
  const props: ResultListSectionProps = {
    keyword: '결제',
    scope: [],
    dateRange: undefined,
    smartFilter: true,
    sortOrder: 'newest',
    active: 'all',
    page: 1,
    onPageChange: () => {},
    selectedId: null,
    onSelectSource: () => {},
    ...overrides,
  };

  return renderWithClient(<ResultListSection {...props} />);
}

// 50개까지 받을 수 있으나 페이지네이션 테스트는 11+개로 충분.
export function makeMockResults(count: number, source = 'jira') {
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
