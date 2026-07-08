'use client';

import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, within } from 'storybook/test';

import type { RagSourceUiModel } from '@/shared/types/ragSourceModel';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import HybridSearchResultCard from './HybridSearchResultCard';

type ResultCardPreset = 'jira' | 'github' | 'slack' | 'channel-talk-document' | 'confluence';

interface HybridSearchResultCardStoryArgs {
  sourcePreset: ResultCardPreset;
  selected: boolean;
  onSelect: (source: RagSourceUiModel) => void;
}

const presetOptions: readonly ResultCardPreset[] = [
  'jira',
  'github',
  'slack',
  'channel-talk-document',
  'confluence',
];

const sourceFixtures: Record<ResultCardPreset, RagSourceUiModel> = {
  jira: {
    id: 'storybook-jira-issue',
    source_type: 'jira',
    entity_type: 'issue',
    is_cited: false,
    repo: 'CU Product',
    title: '결제 승인 플로우 재정리',
    content: '결제 승인 자동화에서 승인 대기 상태와 재시도 정책을 분리합니다.',
    date: '2026. 04. 22.',
    author: 'Product Ops',
    html_url: 'https://example.com/jira/CU-248',
    source_index: 0,
    issue_key: 'CU-248',
  },
  github: {
    id: 'storybook-github-pr',
    source_type: 'github',
    entity_type: 'pr',
    is_cited: false,
    repo: 'catchup/frontend',
    title: '검색 결과 카드 선택 상태 정리',
    content: '선택된 검색 결과를 원문 패널과 동기화하는 UI 변경입니다.',
    date: '2026. 04. 21.',
    author: 'frontend-bot',
    html_url: 'https://example.com/github/catchup/frontend/pull/132',
    source_index: 1,
    github_number: 132,
  },
  slack: {
    id: 'storybook-slack-message',
    source_type: 'slack',
    entity_type: 'message',
    is_cited: false,
    repo: '#product-search',
    title: '스마트 필터는 날짜 조건을 유지한 채 툴 필터만 추론하면 좋겠습니다.',
    content: '스마트 필터 추론 결과를 검색 조건 라벨에 같이 표시합니다.',
    date: '2026. 04. 20.',
    author: '이서연',
    html_url: 'https://example.com/slack/archives/C123/p1713600000000000',
    source_index: 2,
  },
  'channel-talk-document': {
    id: 'storybook-channel-talk-document',
    source_type: 'channel_talk',
    entity_type: 'document_article',
    is_cited: false,
    repo: '고객지원 센터',
    title: '정기 결제 승인 실패 안내',
    content: '카드사 승인 실패 시 고객에게 노출되는 안내 문구와 재시도 정책입니다.',
    date: '2026. 04. 19.',
    author: 'Support Team',
    html_url: 'https://example.com/channel-talk/articles/payment-fail',
    source_index: 3,
  },
  confluence: {
    id: 'storybook-confluence-page',
    source_type: 'confluence',
    entity_type: 'page',
    is_cited: false,
    repo: 'Growth Docs',
    title: 'Q2 검색 품질 실험 계획',
    content: '검색 결과 랭킹과 원문 패널 노출 순서를 실험합니다.',
    date: '2026. 04. 18.',
    author: 'Growth Squad',
    html_url: 'https://example.com/confluence/pages/search-quality',
    source_index: 4,
  },
};

function ResultCardStorySurface(args: HybridSearchResultCardStoryArgs) {
  const source = sourceFixtures[args.sourcePreset];

  return (
    <div className="bg-fill-normal-normal flex min-h-100 items-start justify-center p-6">
      <div className="w-160 max-w-full">
        <HybridSearchResultCard source={source} isSelected={args.selected} onSelect={args.onSelect} />
      </div>
    </div>
  );
}

const meta = {
  title: 'Compositions/Hybrid Search/Results/HybridSearchResultCard',
  tags: ['autodocs'],
  args: {
    sourcePreset: 'jira',
    selected: false,
    onSelect: fn(),
  },
  argTypes: {
    sourcePreset: {
      control: 'select',
      options: presetOptions,
    },
    selected: {
      control: 'boolean',
    },
    onSelect: {
      control: false,
    },
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'hybrid-search',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      designSource: 'dev-preview',
      states: ['source-variant', 'selected', 'unselected', 'metadata'],
      dataNotes: ['Fixture data covers Jira, GitHub, Slack, ChannelTalk document, and Confluence source shapes.'],
      reuseNotes: ['The card reuses shared RagSourceUiModel normalization output used by chat source cards.'],
      interactionNotes: ['Actions log card selection with the selected RagSourceUiModel payload.'],
    }),
  },
} satisfies Meta<HybridSearchResultCardStoryArgs>;

export default meta;

type Story = StoryObj<HybridSearchResultCardStoryArgs>;

export const Playground: Story = {
  render: (args) => <ResultCardStorySurface {...args} />,
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);
    const card = canvas.getByRole('button');

    await userEvent.click(card);
    await expect(args.onSelect).toHaveBeenCalledWith(sourceFixtures[args.sourcePreset]);
  },
};

export const SourceVariants: Story = {
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'hybrid-search',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      designSource: 'dev-preview',
      states: ['jira', 'github', 'slack', 'channel-talk-document', 'confluence'],
    }),
  },
  render: (args) => (
    <div className="bg-fill-normal-normal flex min-h-180 items-start justify-center p-6">
      <div className="flex w-180 max-w-full flex-col gap-1">
        {presetOptions.map((preset, index) => {
          const source = sourceFixtures[preset];

          return (
            <HybridSearchResultCard
              key={source.id}
              source={source}
              isSelected={args.selected && index === 1}
              onSelect={args.onSelect}
            />
          );
        })}
      </div>
    </div>
  ),
};

export const Selected: Story = {
  args: {
    selected: true,
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'hybrid-search',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      designSource: 'dev-preview',
      states: ['selected'],
    }),
  },
  render: (args) => <ResultCardStorySurface {...args} />,
};
