'use client';

import { useState } from 'react';
import type { DateRange } from 'react-day-picker';
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { http, HttpResponse } from 'msw';
import { expect, fn, userEvent, within } from 'storybook/test';

import { API } from '@/shared/api/endpoints';
import type { RagSourceUiModel } from '@/shared/types/ragSourceModel';
import type { SourceResponseApi } from '@/shared/types/sourceApi';
import type { SortOrder } from '@/shared/utils/temporalRange';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import type { ActiveTab, HybridSearchResponse, ToolFilter } from '../../types/hybridSearchApi';
import ResultListSection from './ResultListSection';

interface ResultListSectionStoryArgs {
  keyword: string;
  active: ActiveTab;
  page: number;
  selectedId: string | null;
  sortOrder: SortOrder;
  smartFilter: boolean;
  withToolFilter: boolean;
  withDateRange: boolean;
  onPageChange: (next: number) => void;
  onSelectSource: (source: RagSourceUiModel) => void;
}

const allToolFilters: ToolFilter[] = ['jira', 'github', 'slack', 'confluence', 'channel_talk'];
const filteredTools: ToolFilter[] = ['jira', 'github'];
const storyDateRange: DateRange = {
  from: new Date(2026, 3, 15),
  to: new Date(2026, 3, 22),
};
const sortOptions: readonly SortOrder[] = ['relevance', 'newest', 'oldest'];
const activeOptions: readonly ActiveTab[] = ['all', ...allToolFilters];

function makeJiraResult(index: number): SourceResponseApi {
  return {
    id: `storybook-jira-${index}`,
    source: 'jira',
    entity_type: 'issue',
    title: `결제 승인 자동화 이슈 ${index}`,
    text: '승인 실패 후 재시도 정책과 운영자 확인 단계를 정리합니다.',
    url: `https://example.com/jira/CU-${240 + index}`,
    created_at: `2026-04-${String(10 + (index % 15)).padStart(2, '0')}T01:00:00.000Z`,
    updated_at: `2026-04-${String(12 + (index % 12)).padStart(2, '0')}T04:00:00.000Z`,
    author: index % 2 === 0 ? 'Product Ops' : 'Support Ops',
    index,
    relevance_score: 1 - index * 0.02,
    issue_key: `CU-${240 + index}`,
    project_key: 'CU',
    status: index % 2 === 0 ? 'In Progress' : 'Backlog',
  };
}

const defaultResults: SourceResponseApi[] = [
  {
    id: 'storybook-jira-main',
    source: 'jira',
    entity_type: 'issue',
    title: '결제 승인 플로우 재정리',
    text: '승인 대기 상태와 재시도 정책을 분리하고 운영자 알림 조건을 추가합니다.',
    url: 'https://example.com/jira/CU-248',
    created_at: '2026-04-18T01:00:00.000Z',
    updated_at: '2026-04-22T05:30:00.000Z',
    author: 'Product Ops',
    index: 0,
    relevance_score: 0.98,
    issue_key: 'CU-248',
    project_key: 'CU',
    status: 'In Progress',
  },
  {
    id: 'storybook-github-main',
    source: 'github',
    entity_type: 'pr',
    title: '검색 결과 카드 선택 상태 정리',
    text: '검색 결과 선택 상태를 URL 상태와 원문 패널에 동기화합니다.',
    url: 'https://example.com/github/catchup/frontend/pull/132',
    created_at: '2026-04-17T02:10:00.000Z',
    updated_at: '2026-04-21T09:00:00.000Z',
    author: 'frontend-bot',
    index: 1,
    relevance_score: 0.91,
    owner: 'catchup',
    repo: 'frontend',
    number: 132,
    state: 'open',
  },
  {
    id: 'storybook-slack-main',
    source: 'slack',
    entity_type: 'message',
    title: '스마트 필터는 날짜 조건을 유지한 채 툴 필터만 추론하면 좋겠습니다.',
    text: '검색 조건 라벨에서 추론된 필터와 직접 선택한 필터가 섞이지 않게 분리합니다.',
    url: 'https://example.com/slack/archives/C123/p1713600000000000',
    created_at: '2026-04-20T03:20:00.000Z',
    updated_at: null,
    author: '이서연',
    index: 2,
    relevance_score: 0.84,
    team_id: 'T123',
    channel_name: 'product-search',
    ts: '1713600000.000000',
    thread_ts: '1713600000.000000',
  },
  {
    id: 'storybook-channel-talk-main',
    source: 'channel_talk',
    entity_type: 'document_article',
    title: '정기 결제 승인 실패 안내',
    text: '카드사 승인 실패 시 고객에게 노출되는 안내 문구와 재시도 정책입니다.',
    url: 'https://example.com/channel-talk/articles/payment-fail',
    created_at: '2026-04-19T04:30:00.000Z',
    updated_at: '2026-04-19T08:00:00.000Z',
    author: 'Support Team',
    index: 3,
    relevance_score: 0.79,
    space_name: '고객지원 센터',
    article_id: 'article-payment-fail',
  },
  {
    id: 'storybook-confluence-main',
    source: 'confluence',
    entity_type: 'page',
    title: 'Q2 검색 품질 실험 계획',
    text: '검색 결과 랭킹과 원문 패널 노출 순서를 실험합니다.',
    url: 'https://example.com/confluence/pages/search-quality',
    created_at: '2026-04-16T01:00:00.000Z',
    updated_at: '2026-04-18T07:00:00.000Z',
    author: 'Growth Squad',
    index: 4,
    relevance_score: 0.72,
    space_id: 'SPACE-SEARCH',
    space_key: 'GROWTH',
    space_name: 'Growth Docs',
  },
];

const paginatedResults = Array.from({ length: 16 }, (_, index) => makeJiraResult(index + 1));
const filteredResults = [...defaultResults.slice(0, 2), makeJiraResult(10), makeJiraResult(11)];

function sourceDistribution(results: readonly SourceResponseApi[]): Record<string, number> {
  return results.reduce<Record<string, number>>((acc, result) => {
    acc[result.source] = (acc[result.source] ?? 0) + 1;
    return acc;
  }, {});
}

function makeHybridSearchResponse(results: SourceResponseApi[]): HybridSearchResponse {
  return {
    results,
    total: results.length,
    source_distribution: sourceDistribution(results),
    effective_tool_filters: null,
    effective_start_date: null,
    effective_end_date: null,
    is_tool_filter_inferred: false,
    is_date_filter_inferred: false,
  };
}

function resultsHandler(results: SourceResponseApi[]) {
  return http.get(API.search.hybrid, () => HttpResponse.json(makeHybridSearchResponse(results)));
}

const loadingHandler = http.get(API.search.hybrid, () => new Promise<never>(() => undefined));
const errorHandler = http.get(API.search.hybrid, () => new HttpResponse(null, { status: 500 }));

function StatefulResultListSection(args: ResultListSectionStoryArgs) {
  const [page, setPage] = useState(args.page);
  const [selectedId, setSelectedId] = useState<string | null>(args.selectedId);
  const tools = args.withToolFilter ? filteredTools : [];
  const dateRange = args.withDateRange ? storyDateRange : undefined;

  return (
    <div className="bg-fill-normal-normal flex min-h-180 justify-center p-6">
      <div className="w-250 max-w-full">
        <ResultListSection
          keyword={args.keyword}
          scope={allToolFilters}
          tools={tools}
          dateRange={dateRange}
          smartFilter={args.smartFilter}
          sortOrder={args.sortOrder}
          active={args.active}
          page={page}
          onPageChange={(next) => {
            setPage(next);
            args.onPageChange(next);
          }}
          selectedId={selectedId}
          onSelectSource={(source) => {
            setSelectedId(source.id);
            args.onSelectSource(source);
          }}
        />
      </div>
    </div>
  );
}

const meta = {
  title: 'Compositions/Hybrid Search/Results/ResultListSection',
  tags: ['autodocs'],
  args: {
    keyword: '결제 승인 자동화',
    active: 'all',
    page: 1,
    selectedId: null,
    sortOrder: 'relevance',
    smartFilter: true,
    withToolFilter: false,
    withDateRange: false,
    onPageChange: fn(),
    onSelectSource: fn(),
  },
  argTypes: {
    active: {
      control: 'select',
      options: activeOptions,
    },
    sortOrder: {
      control: 'select',
      options: sortOptions,
    },
    page: {
      control: { type: 'number', min: 1, max: 2, step: 1 },
    },
    selectedId: {
      control: 'text',
    },
    smartFilter: {
      control: 'boolean',
    },
    withToolFilter: {
      control: 'boolean',
    },
    withDateRange: {
      control: 'boolean',
    },
    onPageChange: { control: false },
    onSelectSource: { control: false },
  },
  parameters: {
    msw: {
      handlers: [resultsHandler(defaultResults)],
    },
    ...catchupParameters({
      level: 'composition',
      domain: 'hybrid-search',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'msw',
      designSource: 'dev-preview',
      states: ['results', 'filter-summary', 'pagination', 'empty', 'loading', 'error'],
      dataNotes: ['MSW intercepts GET /api/v1/search/hybrid with realistic source payloads.'],
      reuseNotes: ['The story renders production result states, cards, labels, pagination, and query hook.'],
      interactionNotes: ['Actions log card selection and pagination changes.'],
    }),
  },
} satisfies Meta<ResultListSectionStoryArgs>;

export default meta;

type Story = StoryObj<ResultListSectionStoryArgs>;

export const ResultsDefault: Story = {
  render: (args) => <StatefulResultListSection key={`${args.keyword}:${args.active}`} {...args} />,
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);
    const resultTitle = await canvas.findByText('결제 승인 플로우 재정리');
    const card = resultTitle.closest('[role="button"]');

    await expect(card).not.toBeNull();
    if (!card) return;

    await userEvent.click(card);
    await expect(args.onSelectSource).toHaveBeenCalled();
  },
};

export const FilterSummary: Story = {
  args: {
    keyword: '최근 결제 승인',
    withToolFilter: true,
    withDateRange: true,
    sortOrder: 'newest',
  },
  parameters: {
    msw: {
      handlers: [resultsHandler(filteredResults)],
    },
    ...catchupParameters({
      level: 'composition',
      domain: 'hybrid-search',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'msw',
      designSource: 'dev-preview',
      states: ['filter-summary', 'date-range', 'tool-filter', 'result-count'],
    }),
  },
  render: (args) => <StatefulResultListSection key={`${args.keyword}:${args.sortOrder}`} {...args} />,
};

export const Pagination: Story = {
  args: {
    keyword: '페이지네이션 결제 이슈',
    withToolFilter: true,
    withDateRange: true,
  },
  parameters: {
    msw: {
      handlers: [resultsHandler(paginatedResults)],
    },
    ...catchupParameters({
      level: 'composition',
      domain: 'hybrid-search',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'msw',
      designSource: 'dev-preview',
      states: ['pagination', 'page-change'],
    }),
  },
  render: (args) => <StatefulResultListSection key={args.keyword} {...args} />,
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);
    const pageTwo = await canvas.findByRole('button', { name: /^2$/ });

    await userEvent.click(pageTwo);
    await expect(args.onPageChange).toHaveBeenCalledWith(2);
    await expect(await canvas.findByText('결제 승인 자동화 이슈 11')).toBeInTheDocument();
  },
};

export const EmptyKeyword: Story = {
  args: {
    keyword: '',
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'hybrid-search',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'empty',
      designSource: 'dev-preview',
      states: ['empty-keyword'],
    }),
  },
  render: (args) => <StatefulResultListSection key="empty-keyword" {...args} />,
};

export const Loading: Story = {
  args: {
    keyword: 'loading-state',
  },
  parameters: {
    msw: {
      handlers: [loadingHandler],
    },
    ...catchupParameters({
      level: 'composition',
      domain: 'hybrid-search',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'loading',
      designSource: 'dev-preview',
      states: ['loading'],
    }),
  },
  render: (args) => <StatefulResultListSection key="loading-state" {...args} />,
};

export const Error: Story = {
  args: {
    keyword: 'error-state',
  },
  parameters: {
    msw: {
      handlers: [errorHandler],
    },
    ...catchupParameters({
      level: 'composition',
      domain: 'hybrid-search',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'error',
      designSource: 'dev-preview',
      states: ['error'],
    }),
  },
  render: (args) => <StatefulResultListSection key="error-state" {...args} />,
};
