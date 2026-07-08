import type { Meta, StoryObj } from '@storybook/nextjs-vite';

import { catchupParameters } from '../../../../../../.storybook/catchupStoryParameters';
import type { AgentStudioCardModel } from '../../../types/agentStudioModel';
import AgentCard from './AgentCard';
import AgentStatusSection, { type AgentStatusSectionLabel } from './AgentStatusSection';

interface AgentStatusSectionStoryArgs {
  label: AgentStatusSectionLabel;
  count: number;
  withCard: boolean;
}

const labelOptions: readonly AgentStatusSectionLabel[] = ['운영중', '제작중', '사용 안함'];

const statusByLabel = {
  운영중: 'active',
  제작중: 'draft',
  '사용 안함': 'inactive',
} satisfies Record<AgentStatusSectionLabel, AgentStudioCardModel['status']>;

function makeAgent(label: AgentStatusSectionLabel): AgentStudioCardModel {
  return {
    id: `status-section-${statusByLabel[label]}`,
    agentSpecId: 7101,
    status: statusByLabel[label],
    title: `${label} 문의 대응 Agent`,
    description: '상태 섹션 안에서 카드가 어떤 밀도와 폭으로 배치되는지 확인합니다.',
    authorName: '이진수',
    authorProfileImageUrl: null,
    updatedAtLabel: '2026.07.08(수)',
    isEditable: true,
  };
}

const meta = {
  title: 'Compositions/Agent Studio/List/AgentStatusSection',
  component: AgentStatusSection,
  tags: ['autodocs'],
  args: {
    label: '운영중',
    count: 1,
    withCard: true,
  },
  argTypes: {
    label: {
      control: 'inline-radio',
      options: labelOptions,
    },
    count: {
      control: { type: 'number', min: 0, max: 12, step: 1 },
    },
    withCard: {
      control: 'boolean',
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
      states: ['active-section', 'draft-section', 'inactive-section', 'empty-content'],
      reuseNotes: ['AgentStatusSection owns the status-column header and count treatment.'],
    }),
  },
} satisfies Meta<AgentStatusSectionStoryArgs>;

export default meta;

type Story = StoryObj<AgentStatusSectionStoryArgs>;

export const Playground: Story = {
  render: ({ label, count, withCard }) => (
    <div className="bg-fill-normal-normal flex min-h-96 items-start p-6">
      <AgentStatusSection label={label} count={count} className="max-w-100">
        {withCard ? (
          <AgentCard agent={makeAgent(label)} />
        ) : (
          <div className="text-body-small text-text-normal-assistive flex h-48 w-full items-center justify-center">
            Section body placeholder
          </div>
        )}
      </AgentStatusSection>
    </div>
  ),
};

export const StateSet: Story = {
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'agent-studio',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      designSource: 'figma',
      states: ['active-section', 'draft-section', 'inactive-section'],
    }),
  },
  render: () => (
    <div className="bg-fill-normal-normal flex min-h-96 flex-wrap items-start gap-6 p-6">
      {labelOptions.map((label) => (
        <AgentStatusSection key={label} label={label} count={label === '운영중' ? 3 : 1}>
          <AgentCard agent={makeAgent(label)} />
        </AgentStatusSection>
      ))}
    </div>
  ),
};
