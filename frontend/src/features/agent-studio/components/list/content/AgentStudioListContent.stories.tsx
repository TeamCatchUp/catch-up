import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../.storybook/catchupStoryParameters';
import type { AgentStudioCardModel, AgentStudioFilter } from '../../../types/agentStudioModel';
import AgentStudioListContent from './AgentStudioListContent';

interface AgentStudioListContentStoryArgs {
  selectedFilter: AgentStudioFilter;
  dataset: 'mixed' | 'active-only' | 'empty';
  actionDisabled: boolean;
  onActivate: (agent: AgentStudioCardModel) => void;
  onDeactivate: (agent: AgentStudioCardModel) => void;
  onEdit: (agent: AgentStudioCardModel) => void;
}

const filterOptions: readonly AgentStudioFilter[] = ['all', 'active', 'draft', 'inactive'];
const datasetOptions: readonly AgentStudioListContentStoryArgs['dataset'][] = ['mixed', 'active-only', 'empty'];

const mixedAgents: readonly AgentStudioCardModel[] = [
  {
    id: 'story-agent-active',
    agentSpecId: 101,
    status: 'active',
    title: '문의 대응 리포트 만들기',
    description: '채널톡 문의를 읽고 Slack으로 대응 리포트를 보냅니다.',
    authorName: '이진수',
    authorProfileImageUrl: null,
    updatedAtLabel: '2026.07.08(수)',
    isEditable: true,
  },
  {
    id: 'story-agent-draft',
    agentSpecId: 102,
    status: 'draft',
    title: 'VIP 문의 우선 정리',
    description: '우선순위가 높은 고객 문의를 별도 채널로 정리합니다.',
    authorName: '김서연',
    authorProfileImageUrl: null,
    updatedAtLabel: '2026.07.07(화)',
    isEditable: true,
  },
  {
    id: 'story-agent-inactive',
    agentSpecId: 103,
    status: 'inactive',
    title: '주간 문의 요약',
    description: '운영이 중지된 문의 요약 Agent입니다.',
    authorName: '박민재',
    authorProfileImageUrl: null,
    updatedAtLabel: '2026.07.01(수)',
    isEditable: true,
  },
  {
    id: 'story-agent-readonly',
    agentSpecId: 104,
    status: 'active',
    title: 'CS 핸드오프 알림',
    description: '다른 구성원이 만든 읽기 전용 Agent입니다.',
    authorName: '정하린',
    authorProfileImageUrl: null,
    updatedAtLabel: '2026.06.30(화)',
    isEditable: false,
  },
];

const activeAgents = mixedAgents.filter((agent) => agent.status === 'active');

function getAgents(dataset: AgentStudioListContentStoryArgs['dataset']) {
  if (dataset === 'active-only') return activeAgents;
  if (dataset === 'empty') return [];
  return mixedAgents;
}

const meta = {
  title: 'Compositions/Agent Studio/List/AgentStudioListContent',
  component: AgentStudioListContent,
  tags: ['autodocs'],
  args: {
    selectedFilter: 'all',
    dataset: 'mixed',
    actionDisabled: false,
    onActivate: fn(),
    onDeactivate: fn(),
    onEdit: fn(),
  },
  argTypes: {
    selectedFilter: {
      control: 'inline-radio',
      options: filterOptions,
    },
    dataset: {
      control: 'inline-radio',
      options: datasetOptions,
    },
    actionDisabled: {
      control: 'boolean',
    },
    onActivate: {
      control: false,
    },
    onDeactivate: {
      control: false,
    },
    onEdit: {
      control: false,
    },
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'agent-studio',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      designSource: 'figma',
      states: ['mixed-grouped', 'filtered-grid', 'empty-filter', 'readonly-card'],
      dataNotes: ['Uses story-local fixture data that includes active, draft, inactive, and readonly agents.'],
      reuseNotes: ['This is the assembled list body below AgentFilterTabs and above the screen shell.'],
      interactionNotes: ['Editable card menus and inactive restore actions are delegated to AgentCard.'],
    }),
  },
} satisfies Meta<AgentStudioListContentStoryArgs>;

export default meta;

type Story = StoryObj<AgentStudioListContentStoryArgs>;

export const Playground: Story = {
  render: ({ selectedFilter, dataset, actionDisabled, onActivate, onDeactivate, onEdit }) => (
    <div className="bg-fill-normal-normal flex min-h-100 flex-wrap items-start gap-6 p-6">
      <AgentStudioListContent
        agents={getAgents(dataset)}
        selectedFilter={selectedFilter}
        actionDisabled={actionDisabled}
        onActivate={onActivate}
        onDeactivate={onDeactivate}
        onEdit={onEdit}
      />
    </div>
  ),
  play: async ({ args, canvasElement, step, userEvent }) => {
    const canvas = within(canvasElement);

    await step('restore inactive agent', async () => {
      await userEvent.click(canvas.getByRole('button', { name: '다시 운영하기' }));
      await expect(args.onActivate).toHaveBeenCalled();
    });
  },
};

export const DraftEmpty: Story = {
  args: {
    selectedFilter: 'draft',
    dataset: 'active-only',
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'agent-studio',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'empty',
      designSource: 'figma',
      states: ['empty-filter'],
    }),
  },
  render: (args) => (
    <div className="bg-fill-normal-normal flex min-h-80 flex-wrap items-start gap-6 p-6">
      <AgentStudioListContent
        agents={getAgents(args.dataset)}
        selectedFilter={args.selectedFilter}
        actionDisabled={args.actionDisabled}
        onActivate={args.onActivate}
        onDeactivate={args.onDeactivate}
        onEdit={args.onEdit}
      />
    </div>
  ),
};
