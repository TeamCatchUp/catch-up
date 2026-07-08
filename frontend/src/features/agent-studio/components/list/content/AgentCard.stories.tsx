import type { ReactNode } from 'react';
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../.storybook/catchupStoryParameters';
import type { AgentStudioCardModel } from '../../../types/agentStudioModel';
import AgentCard from './AgentCard';

interface AgentCardStoryArgs {
  status: AgentStudioCardModel['status'];
  isEditable: boolean;
  actionDisabled: boolean;
  layout: 'section' | 'grid';
  onActivate: (agent: AgentStudioCardModel) => void;
  onDeactivate: (agent: AgentStudioCardModel) => void;
  onEdit: (agent: AgentStudioCardModel) => void;
}

const agentStatusOptions: readonly AgentStudioCardModel['status'][] = ['active', 'draft', 'inactive'];

const statusDescription = {
  active: '운영 중인 Agent 카드입니다. 메뉴에서 수정하거나 사용을 중지할 수 있습니다.',
  draft: '제작 중인 Agent 카드입니다. 설정을 이어서 편집할 수 있습니다.',
  inactive: '사용하지 않는 Agent 카드입니다. 다시 운영하기 액션이 노출됩니다.',
} satisfies Record<AgentStudioCardModel['status'], string>;

function makeAgent(status: AgentStudioCardModel['status'], isEditable: boolean): AgentStudioCardModel {
  return {
    id: `story-${status}-${isEditable ? 'editable' : 'readonly'}`,
    agentSpecId: 9001,
    status,
    title: status === 'inactive' ? '비활성 문의 대응 Agent' : '문의 대응 리포트 만들기',
    description: statusDescription[status],
    authorName: isEditable ? '이진수' : '김서연',
    authorProfileImageUrl: null,
    updatedAtLabel: status === 'draft' ? '2026.07.08(수)' : '2026.07.07(화)',
    isEditable,
  };
}

function AgentCardFrame({ children }: { children: ReactNode }) {
  return <div className="bg-fill-normal-normal flex min-h-72 items-start p-6">{children}</div>;
}

const meta = {
  title: 'Compositions/Agent Studio/List/AgentCard',
  component: AgentCard,
  tags: ['autodocs'],
  args: {
    status: 'active',
    isEditable: true,
    actionDisabled: false,
    layout: 'section',
    onActivate: fn(),
    onDeactivate: fn(),
    onEdit: fn(),
  },
  argTypes: {
    status: {
      control: 'inline-radio',
      options: agentStatusOptions,
    },
    isEditable: {
      control: 'boolean',
    },
    actionDisabled: {
      control: 'boolean',
    },
    layout: {
      control: 'inline-radio',
      options: ['section', 'grid'],
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
      states: ['active', 'draft', 'inactive', 'readonly', 'action-disabled'],
      reuseNotes: ['AgentCard is the entity-like visual unit inside the Agent Studio list workflow.'],
      interactionNotes: ['Editable active cards expose menu actions; inactive cards expose restore action.'],
    }),
  },
} satisfies Meta<AgentCardStoryArgs>;

export default meta;

type Story = StoryObj<AgentCardStoryArgs>;

export const Playground: Story = {
  render: ({ status, isEditable, actionDisabled, layout, onActivate, onDeactivate, onEdit }) => (
    <AgentCardFrame>
      <AgentCard
        agent={makeAgent(status, isEditable)}
        actionDisabled={actionDisabled}
        layout={layout}
        onActivate={onActivate}
        onDeactivate={onDeactivate}
        onEdit={onEdit}
      />
    </AgentCardFrame>
  ),
  play: async ({ args, canvasElement, step, userEvent }) => {
    const canvas = within(canvasElement);
    const portal = within(document.body);

    if (args.status === 'inactive') {
      await step('restore inactive agent', async () => {
        await userEvent.click(canvas.getByRole('button', { name: '다시 운영하기' }));
        await expect(args.onActivate).toHaveBeenCalled();
      });
      return;
    }

    if (!args.isEditable || args.actionDisabled) return;

    await step('open card menu and edit', async () => {
      await userEvent.click(canvas.getByRole('button', { name: /카드 메뉴/ }));
      await userEvent.click(await portal.findByRole('menuitem', { name: '수정하기' }));
      await expect(args.onEdit).toHaveBeenCalled();
    });
  },
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
      states: ['active', 'draft', 'inactive', 'readonly'],
    }),
  },
  render: (args) => (
    <div className="bg-fill-normal-normal flex min-h-96 flex-wrap items-start gap-4 p-6">
      {agentStatusOptions.map((status) => (
        <AgentCard
          key={status}
          agent={makeAgent(status, true)}
          actionDisabled={args.actionDisabled}
          layout="grid"
          onActivate={args.onActivate}
          onDeactivate={args.onDeactivate}
          onEdit={args.onEdit}
        />
      ))}
      <AgentCard agent={makeAgent('active', false)} layout="grid" />
    </div>
  ),
};
