'use client';

import { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, within } from 'storybook/test';

import type { RagSourceUiModel } from '@/shared/types/ragSourceModel';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import OriginalPanelComingSoon from '../original/shared/states/OriginalPanelComingSoon';
import OriginalPanelEmpty from '../original/shared/states/OriginalPanelEmpty';
import HybridSearchResultCard from '../result-list/HybridSearchResultCard';
import ResultPageBody from './ResultPageBody';

type SidePanelState = 'empty' | 'coming-soon';

interface ResultPageBodyStoryArgs {
  selectedId: string | null;
  sidePanelState: SidePanelState;
  onSelectSource: (source: RagSourceUiModel) => void;
}

const sidePanelOptions: readonly SidePanelState[] = ['empty', 'coming-soon'];

const screenSources: RagSourceUiModel[] = [
  {
    id: 'screen-jira-main',
    source_type: 'jira',
    entity_type: 'issue',
    is_cited: false,
    repo: 'CU Product',
    title: '결제 승인 플로우 재정리',
    content: '승인 대기 상태와 재시도 정책을 분리하고 운영자 알림 조건을 추가합니다.',
    date: '2026. 04. 22.',
    author: 'Product Ops',
    html_url: 'https://example.com/jira/CU-248',
    source_index: 0,
    issue_key: 'CU-248',
  },
  {
    id: 'screen-github-main',
    source_type: 'github',
    entity_type: 'pr',
    is_cited: false,
    repo: 'catchup/frontend',
    title: '검색 결과 카드 선택 상태 정리',
    content: '검색 결과 선택 상태를 URL 상태와 원문 패널에 동기화합니다.',
    date: '2026. 04. 21.',
    author: 'frontend-bot',
    html_url: 'https://example.com/github/catchup/frontend/pull/132',
    source_index: 1,
    github_number: 132,
  },
  {
    id: 'screen-slack-main',
    source_type: 'slack',
    entity_type: 'message',
    is_cited: false,
    repo: '#product-search',
    title: '스마트 필터는 날짜 조건을 유지한 채 툴 필터만 추론하면 좋겠습니다.',
    content: '검색 조건 라벨에서 추론된 필터와 직접 선택한 필터가 섞이지 않게 분리합니다.',
    date: '2026. 04. 20.',
    author: '이서연',
    html_url: 'https://example.com/slack/archives/C123/p1713600000000000',
    source_index: 2,
  },
];

function StoryHeader() {
  return (
    <header className="border-line-normal-neutral flex h-25 shrink-0 items-center justify-center border-b px-16">
      <div className="flex w-full max-w-355 items-center justify-between gap-6">
        <div className="flex flex-col gap-1">
          <span className="text-heading-small text-text-normal-normal font-semibold">결제 승인 자동화</span>
          <span className="text-body-small text-text-normal-assistive">Jira, GitHub, Slack에서 찾은 검색 결과</span>
        </div>
        <span className="text-body-small text-text-normal-alternative">최근 7일 · 관련도순</span>
      </div>
    </header>
  );
}

function ResultPageBodySurface(args: ResultPageBodyStoryArgs) {
  const [selectedId, setSelectedId] = useState(args.selectedId);
  const selectedSource = screenSources.find((source) => source.id === selectedId);
  const sidePanelState = selectedSource ? args.sidePanelState : 'empty';

  return (
    <div className="bg-fill-normal-normal flex h-dvh min-h-180 flex-col">
      <StoryHeader />
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
          {screenSources.map((source) => (
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
    selectedId: 'screen-jira-main',
    sidePanelState: 'coming-soon',
    onSelectSource: fn(),
  },
  argTypes: {
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
  },
  parameters: {
    ...catchupParameters({
      level: 'screen',
      domain: 'hybrid-search',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      designSource: 'dev-preview',
      viewport: { width: 1440, height: 900 },
      states: ['desktop-shell', 'result-list', 'side-panel', 'selected-result'],
      layoutNotes: [
        'This screen story verifies the production ResultPageBody scroll boundary and side-panel width.',
        'The full App Router page is intentionally not mocked here; URL/query behavior remains covered by composition stories.',
      ],
      reuseNotes: ['The story uses production ResultPageBody, HybridSearchResultCard, and original-panel state components.'],
      interactionNotes: ['Actions log selected result changes from the result list.'],
    }),
  },
} satisfies Meta<ResultPageBodyStoryArgs>;

export default meta;

type Story = StoryObj<ResultPageBodyStoryArgs>;

export const Default: Story = {
  render: (args) => <ResultPageBodySurface key={`${args.selectedId}:${args.sidePanelState}`} {...args} />,
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);
    const slackTitle = canvas.getByText(/스마트 필터는 날짜 조건을 유지한 채 툴 필터만 추론하면 좋겠습니다/);
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
      dataProfile: 'empty',
      designSource: 'dev-preview',
      viewport: { width: 1440, height: 900 },
      states: ['desktop-shell', 'result-list', 'empty-side-panel'],
    }),
  },
  render: (args) => <ResultPageBodySurface key={`${args.selectedId}:${args.sidePanelState}`} {...args} />,
};
