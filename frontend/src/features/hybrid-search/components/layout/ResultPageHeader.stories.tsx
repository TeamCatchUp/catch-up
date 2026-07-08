'use client';

import { useState } from 'react';
import type { DateRange } from 'react-day-picker';
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { http, HttpResponse } from 'msw';
import { expect, fn, userEvent, waitFor, within } from 'storybook/test';

import { API } from '@/shared/api/endpoints';
import type { SourceResponseApi } from '@/shared/types/sourceApi';
import type { SortOrder } from '@/shared/utils/temporalRange';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import type { ActiveTab, HybridSearchResponse, ToolFilter } from '../../types/hybridSearchApi';
import ResultPageHeader from './ResultPageHeader';

interface ResultPageHeaderStoryArgs {
  keyword: string;
  draftKeyword: string;
  activeTab: ActiveTab;
  sortOrder: SortOrder;
  smartFilter: boolean;
  draftSmartFilter: boolean;
  withToolFilter: boolean;
  withDateRange: boolean;
  onDraftKeywordChange: (value: string) => void;
  onDraftChipsChange: (next: ToolFilter[]) => void;
  onDraftDateRangeChange: (next: DateRange | undefined) => void;
  onDraftSmartFilterChange: (next: boolean) => void;
  onSubmit: () => void;
  onHistorySubmit: (query: string) => void;
  onClear: () => void;
  onAiModeClick: () => void;
  onTabChange: (next: ActiveTab) => void;
  onSortChange: (next: SortOrder) => void;
}

const allToolFilters: ToolFilter[] = ['jira', 'github', 'slack', 'confluence', 'channel_talk'];
const filteredTools: ToolFilter[] = ['jira', 'github'];
const activeTabOptions: readonly ActiveTab[] = ['all', ...allToolFilters];
const sortOptions: readonly SortOrder[] = ['relevance', 'newest', 'oldest'];
const storyDateRange: DateRange = {
  from: new Date(2026, 3, 15),
  to: new Date(2026, 3, 22),
};

const headerResults: SourceResponseApi[] = [
  {
    id: 'header-jira-main',
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
    id: 'header-jira-secondary',
    source: 'jira',
    entity_type: 'issue',
    title: '승인 실패 재시도 정책',
    text: '결제 실패 상태와 후속 알림 조건을 재정의합니다.',
    url: 'https://example.com/jira/CU-251',
    created_at: '2026-04-19T01:00:00.000Z',
    updated_at: '2026-04-21T05:30:00.000Z',
    author: 'Support Ops',
    index: 1,
    relevance_score: 0.92,
    issue_key: 'CU-251',
    project_key: 'CU',
    status: 'Backlog',
  },
  {
    id: 'header-slack-main',
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
    id: 'header-github-main',
    source: 'github',
    entity_type: 'pr',
    title: '검색 결과 카드 선택 상태 정리',
    text: '검색 결과 선택 상태를 URL 상태와 원문 패널에 동기화합니다.',
    url: 'https://example.com/github/catchup/frontend/pull/132',
    created_at: '2026-04-17T02:10:00.000Z',
    updated_at: '2026-04-21T09:00:00.000Z',
    author: 'frontend-bot',
    index: 3,
    relevance_score: 0.81,
    owner: 'catchup',
    repo: 'frontend',
    number: 132,
    state: 'open',
  },
];

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

function StatefulResultPageHeader(args: ResultPageHeaderStoryArgs) {
  const [keyword, setKeyword] = useState(args.keyword);
  const [draftKeyword, setDraftKeyword] = useState(args.draftKeyword);
  const [draftChips, setDraftChips] = useState<ToolFilter[]>(args.withToolFilter ? [...filteredTools] : []);
  const [dateRange, setDateRange] = useState<DateRange | undefined>(args.withDateRange ? storyDateRange : undefined);
  const [draftDateRange, setDraftDateRange] = useState<DateRange | undefined>(
    args.withDateRange ? storyDateRange : undefined,
  );
  const [draftSmartFilter, setDraftSmartFilter] = useState(args.draftSmartFilter);
  const [activeTab, setActiveTab] = useState(args.activeTab);
  const [sortOrder, setSortOrder] = useState(args.sortOrder);

  return (
    <div className="bg-fill-normal-normal min-h-80 w-full">
      <ResultPageHeader
        keyword={keyword}
        toolFilters={draftChips}
        draftKeyword={draftKeyword}
        onDraftKeywordChange={(next) => {
          setDraftKeyword(next);
          args.onDraftKeywordChange(next);
        }}
        draftChips={draftChips}
        onDraftChipsChange={(next) => {
          setDraftChips(next);
          args.onDraftChipsChange(next);
        }}
        dateRange={dateRange}
        draftDateRange={draftDateRange}
        onDraftDateRangeChange={(next) => {
          setDraftDateRange(next);
          args.onDraftDateRangeChange(next);
        }}
        smartFilter={args.smartFilter}
        draftSmartFilter={draftSmartFilter}
        onDraftSmartFilterChange={(next) => {
          setDraftSmartFilter(next);
          args.onDraftSmartFilterChange(next);
        }}
        onSubmit={() => {
          setKeyword(draftKeyword);
          setDateRange(draftDateRange);
          args.onSubmit();
        }}
        onHistorySubmit={(query) => {
          setDraftKeyword(query);
          setKeyword(query);
          args.onHistorySubmit(query);
        }}
        onClear={() => {
          setDraftKeyword('');
          args.onClear();
        }}
        onAiModeClick={args.onAiModeClick}
        activeTab={activeTab}
        onTabChange={(next) => {
          setActiveTab(next);
          args.onTabChange(next);
        }}
        sortOrder={sortOrder}
        onSortChange={(next) => {
          setSortOrder(next);
          args.onSortChange(next);
        }}
      />
    </div>
  );
}

const meta = {
  title: 'Compositions/Hybrid Search/Layout/ResultPageHeader',
  tags: ['autodocs'],
  args: {
    keyword: '결제 승인 자동화',
    draftKeyword: '결제 승인 자동화',
    activeTab: 'all',
    sortOrder: 'relevance',
    smartFilter: true,
    draftSmartFilter: true,
    withToolFilter: false,
    withDateRange: false,
    onDraftKeywordChange: fn(),
    onDraftChipsChange: fn(),
    onDraftDateRangeChange: fn(),
    onDraftSmartFilterChange: fn(),
    onSubmit: fn(),
    onHistorySubmit: fn(),
    onClear: fn(),
    onAiModeClick: fn(),
    onTabChange: fn(),
    onSortChange: fn(),
  },
  argTypes: {
    activeTab: {
      control: 'select',
      options: activeTabOptions,
    },
    sortOrder: {
      control: 'select',
      options: sortOptions,
    },
    smartFilter: {
      control: 'boolean',
    },
    draftSmartFilter: {
      control: 'boolean',
    },
    withToolFilter: {
      control: 'boolean',
    },
    withDateRange: {
      control: 'boolean',
    },
    onDraftKeywordChange: { control: false },
    onDraftChipsChange: { control: false },
    onDraftDateRangeChange: { control: false },
    onDraftSmartFilterChange: { control: false },
    onSubmit: { control: false },
    onHistorySubmit: { control: false },
    onClear: { control: false },
    onAiModeClick: { control: false },
    onTabChange: { control: false },
    onSortChange: { control: false },
  },
  parameters: {
    msw: {
      handlers: [resultsHandler(headerResults)],
    },
    ...catchupParameters({
      level: 'composition',
      domain: 'hybrid-search',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'msw',
      designSource: 'dev-preview',
      viewport: { width: 1440, height: 220 },
      states: ['result-search-bar', 'source-tabs', 'source-counts', 'sort-dropdown'],
      dataNotes: ['MSW intercepts GET /api/v1/search/hybrid and the header derives source tab counts from results.'],
      reuseNotes: ['The story renders production ResultPageHeader, ResultSearchBar, AccentTabs, and SortDropdown.'],
      interactionNotes: ['Actions log tab, sort, draft keyword, clear, submit, and AI-mode callbacks.'],
    }),
  },
} satisfies Meta<ResultPageHeaderStoryArgs>;

export default meta;

type Story = StoryObj<ResultPageHeaderStoryArgs>;

export const ResultsTabs: Story = {
  render: (args) => <StatefulResultPageHeader key={`${args.keyword}:${args.activeTab}`} {...args} />,
  play: async ({ args, canvasElement, step }) => {
    const canvas = within(canvasElement);

    await step('show source counts from result payload', async () => {
      const allTab = await canvas.findByRole('tab', { name: /전체/ });
      const jiraTab = canvas.getByRole('tab', { name: /Jira/ });
      const slackTab = canvas.getByRole('tab', { name: /Slack/ });
      const githubTab = canvas.getByRole('tab', { name: /Github/ });

      await waitFor(() => expect(allTab).toHaveTextContent('4'));
      await expect(jiraTab).toHaveTextContent('2');
      await expect(slackTab).toHaveTextContent('1');
      await expect(githubTab).toHaveTextContent('1');
    });

    await step('change active source tab', async () => {
      await userEvent.click(canvas.getByRole('tab', { name: /Slack/ }));
      await expect(args.onTabChange).toHaveBeenCalledWith('slack');
    });
  },
};

export const FilteredDraft: Story = {
  args: {
    keyword: '최근 결제 승인',
    draftKeyword: '최근 결제 승인',
    sortOrder: 'newest',
    withToolFilter: true,
    withDateRange: true,
  },
  render: (args) => <StatefulResultPageHeader key="filtered-draft" {...args} />,
};

export const LoadingTabs: Story = {
  args: {
    keyword: 'loading-state',
    draftKeyword: 'loading-state',
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
      viewport: { width: 1440, height: 220 },
      states: ['loading', 'source-tabs-without-counts'],
      dataNotes: ['Tabs show every source without count badges while the list query is loading.'],
    }),
  },
  render: (args) => <StatefulResultPageHeader key="loading-tabs" {...args} />,
  play: async ({ canvasElement, step }) => {
    const canvas = within(canvasElement);

    await step('show all source tabs without counts', async () => {
      await expect(canvas.getByRole('tab', { name: /^전체$/ })).toBeInTheDocument();
      await expect(canvas.getByRole('tab', { name: /^Jira$/ })).toBeInTheDocument();
      await expect(canvas.getByRole('tab', { name: /^Slack$/ })).toBeInTheDocument();
      await expect(canvas.getByRole('tab', { name: /^Confluence$/ })).toBeInTheDocument();
      await expect(canvas.getByRole('tab', { name: /^Github$/ })).toBeInTheDocument();
      await expect(canvas.getByRole('tab', { name: /^채널톡$/ })).toBeInTheDocument();
    });
  },
};

export const EmptyResults: Story = {
  args: {
    keyword: 'empty-state',
    draftKeyword: 'empty-state',
  },
  parameters: {
    msw: {
      handlers: [resultsHandler([])],
    },
    ...catchupParameters({
      level: 'composition',
      domain: 'hybrid-search',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'empty',
      designSource: 'dev-preview',
      viewport: { width: 1440, height: 220 },
      states: ['empty-results', 'all-tab-only'],
      dataNotes: ['When the query returns no results, only the all tab remains with a zero count.'],
    }),
  },
  render: (args) => <StatefulResultPageHeader key="empty-results" {...args} />,
};
