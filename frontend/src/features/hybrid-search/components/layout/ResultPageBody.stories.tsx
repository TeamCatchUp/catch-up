'use client';

import { useState } from 'react';
import type { DateRange } from 'react-day-picker';
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { http, HttpResponse } from 'msw';
import { expect, fn, userEvent, waitFor, within } from 'storybook/test';

import { API } from '@/shared/api/endpoints';
import type { RagSourceUiModel } from '@/shared/types/ragSourceModel';
import type { SourceResponseApi } from '@/shared/types/sourceApi';
import { normalizeSources } from '@/shared/utils/normalize/normalizeRagSources';
import type { SortOrder } from '@/shared/utils/temporalRange';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import type { ActiveTab, HybridSearchResponse, ToolFilter } from '../../types/hybridSearchApi';
import OriginalPanelComingSoon from '../original/shared/states/OriginalPanelComingSoon';
import OriginalPanelEmpty from '../original/shared/states/OriginalPanelEmpty';
import HybridSearchResultCard from '../result-list/HybridSearchResultCard';
import ResultPageBody from './ResultPageBody';
import ResultPageHeader from './ResultPageHeader';

type SidePanelState = 'empty' | 'coming-soon';

interface ResultPageBodyStoryArgs {
  keyword: string;
  draftKeyword: string;
  activeTab: ActiveTab;
  sortOrder: SortOrder;
  selectedId: string | null;
  sidePanelState: SidePanelState;
  onSelectSource: (source: RagSourceUiModel) => void;
  onTabChange: (next: ActiveTab) => void;
  onSortChange: (next: SortOrder) => void;
  onSubmit: () => void;
  onClear: () => void;
  onAiModeClick: () => void;
}

const activeTabOptions: readonly ActiveTab[] = ['all', 'jira', 'github', 'slack', 'confluence', 'channel_talk'];
const sortOptions: readonly SortOrder[] = ['relevance', 'newest', 'oldest'];
const sidePanelOptions: readonly SidePanelState[] = ['empty', 'coming-soon'];

const screenSearchResults: SourceResponseApi[] = [
  {
    id: 'screen-jira-main',
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
    id: 'screen-github-main',
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
    id: 'screen-slack-main',
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
];

const screenSources = normalizeSources(screenSearchResults);

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

const resultsHandler = http.get(API.search.hybrid, () => HttpResponse.json(makeHybridSearchResponse(screenSearchResults)));

function ResultPageBodySurface(args: ResultPageBodyStoryArgs) {
  const [keyword, setKeyword] = useState(args.keyword);
  const [draftKeyword, setDraftKeyword] = useState(args.draftKeyword);
  const [draftChips, setDraftChips] = useState<ToolFilter[]>([]);
  const [dateRange, setDateRange] = useState<DateRange | undefined>(undefined);
  const [draftDateRange, setDraftDateRange] = useState<DateRange | undefined>(undefined);
  const [draftSmartFilter, setDraftSmartFilter] = useState(true);
  const [activeTab, setActiveTab] = useState(args.activeTab);
  const [sortOrder, setSortOrder] = useState(args.sortOrder);
  const [selectedId, setSelectedId] = useState(args.selectedId);
  const visibleSources =
    activeTab === 'all' ? screenSources : screenSources.filter((source) => source.source_type === activeTab);
  const selectedSource = screenSources.find((source) => source.id === selectedId);
  const sidePanelState = selectedSource ? args.sidePanelState : 'empty';

  return (
    <div className="bg-fill-normal-normal flex h-dvh min-h-180 flex-col">
      <ResultPageHeader
        keyword={keyword}
        toolFilters={draftChips}
        draftKeyword={draftKeyword}
        onDraftKeywordChange={setDraftKeyword}
        draftChips={draftChips}
        onDraftChipsChange={setDraftChips}
        dateRange={dateRange}
        draftDateRange={draftDateRange}
        onDraftDateRangeChange={setDraftDateRange}
        smartFilter
        draftSmartFilter={draftSmartFilter}
        onDraftSmartFilterChange={setDraftSmartFilter}
        onSubmit={() => {
          setKeyword(draftKeyword);
          setDateRange(draftDateRange);
          args.onSubmit();
        }}
        onHistorySubmit={(query) => {
          setDraftKeyword(query);
          setKeyword(query);
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
      <ResultPageBody
        side={
          sidePanelState === 'coming-soon' ? (
            <OriginalPanelComingSoon toolName={selectedSource?.repo ?? '선택한 문서'} />
          ) : (
            <OriginalPanelEmpty />
          )
        }
      >
        <div className="flex w-full flex-col items-start gap-1">
          {visibleSources.map((source) => (
            <HybridSearchResultCard
              key={source.id}
              source={source}
              isSelected={source.id === selectedId}
              onSelect={(nextSource) => {
                setSelectedId(nextSource.id);
                args.onSelectSource(nextSource);
              }}
            />
          ))}
        </div>
      </ResultPageBody>
    </div>
  );
}

const meta = {
  title: 'Screens/Hybrid Search/ResultPageBody',
  tags: ['autodocs'],
  args: {
    keyword: '결제 승인 자동화',
    draftKeyword: '결제 승인 자동화',
    activeTab: 'all',
    sortOrder: 'relevance',
    selectedId: 'screen-jira-main',
    sidePanelState: 'coming-soon',
    onSelectSource: fn(),
    onTabChange: fn(),
    onSortChange: fn(),
    onSubmit: fn(),
    onClear: fn(),
    onAiModeClick: fn(),
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
    selectedId: {
      control: 'text',
    },
    sidePanelState: {
      control: 'select',
      options: sidePanelOptions,
    },
    onSelectSource: {
      control: false,
    },
    onTabChange: { control: false },
    onSortChange: { control: false },
    onSubmit: { control: false },
    onClear: { control: false },
    onAiModeClick: { control: false },
  },
  parameters: {
    msw: {
      handlers: [resultsHandler],
    },
    ...catchupParameters({
      level: 'screen',
      domain: 'hybrid-search',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'msw',
      designSource: 'dev-preview',
      viewport: { width: 1440, height: 900 },
      states: ['desktop-shell', 'result-header', 'result-list', 'side-panel', 'selected-result'],
      layoutNotes: [
        'This screen story verifies the production ResultPageHeader and ResultPageBody vertical composition.',
        'The full App Router page is intentionally not mocked here; URL persistence remains covered by page-level tests.',
      ],
      dataNotes: ['The header query and result cards share the same source fixture set through MSW and normalizeSources.'],
      reuseNotes: [
        'The story uses production ResultPageHeader, ResultPageBody, HybridSearchResultCard, and original-panel state components.',
      ],
      interactionNotes: ['Actions log tab, sort, search submit, AI-mode, clear, and result selection changes.'],
    }),
  },
} satisfies Meta<ResultPageBodyStoryArgs>;

export default meta;

type Story = StoryObj<ResultPageBodyStoryArgs>;

export const Default: Story = {
  render: (args) => (
    <ResultPageBodySurface key={`${args.keyword}:${args.activeTab}:${args.selectedId}:${args.sidePanelState}`} {...args} />
  ),
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);

    const allTab = await canvas.findByRole('tab', { name: /전체/ });
    await waitFor(() => expect(allTab).toHaveTextContent('3'));

    const slackTitle = await canvas.findByText(/스마트 필터는 날짜 조건을 유지한 채 툴 필터만 추론하면 좋겠습니다/);
    const card = slackTitle.closest('[role="button"]');

    await expect(card).not.toBeNull();
    if (!card) return;

    await userEvent.click(card);
    await expect(args.onSelectSource).toHaveBeenCalledWith(screenSources[2]);
  },
};

export const EmptySidePanel: Story = {
  args: {
    selectedId: null,
    sidePanelState: 'empty',
  },
  parameters: {
    ...catchupParameters({
      level: 'screen',
      domain: 'hybrid-search',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'msw',
      designSource: 'dev-preview',
      viewport: { width: 1440, height: 900 },
      states: ['desktop-shell', 'result-header', 'result-list', 'empty-side-panel'],
    }),
  },
  render: (args) => (
    <ResultPageBodySurface key={`${args.keyword}:${args.activeTab}:${args.selectedId}:${args.sidePanelState}`} {...args} />
  ),
};
