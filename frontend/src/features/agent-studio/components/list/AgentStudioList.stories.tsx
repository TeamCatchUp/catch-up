'use client';

import { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { http, HttpResponse } from 'msw';
import { expect, fn, within } from 'storybook/test';

import { API } from '@/shared/api/endpoints';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import {
  AGENT_STUDIO_FILTERS,
  AGENT_STUDIO_MULTI_ACTIVE_LIST_FIXTURE,
} from '../../fixtures/agentStudioFixtures';
import type { AgentStudioCardModel, AgentStudioFilter } from '../../types/agentStudioModel';
import AgentCreateButton from './actions/AgentCreateButton';
import AgentStudioHeader from './AgentStudioHeader';
import AgentStudioListContent from './content/AgentStudioListContent';
import AgentFilterTabs from './filters/AgentFilterTabs';
import AgentStudioListSkeleton from './states/AgentStudioListSkeleton';

interface AgentStudioListStoryArgs {
  selectedFilter: AgentStudioFilter;
  showMineOnly: boolean;
  actionDisabled: boolean;
  onCreate: () => void;
  onFilterChange: (value: AgentStudioFilter) => void;
  onShowMineOnlyChange: (checked: boolean) => void;
  onActivate: (agent: AgentStudioCardModel) => void;
  onDeactivate: (agent: AgentStudioCardModel) => void;
  onEdit: (agent: AgentStudioCardModel) => void;
}

const filterOptions: readonly AgentStudioFilter[] = ['all', 'active', 'draft', 'inactive'];
const agentStudioListHandlers = [http.get(API.version, () => HttpResponse.json('1.2.3'))];

function AgentStudioListSurface({ children }: { children: React.ReactNode }) {
  return (
    <div className="bg-background-normal-normal flex min-h-full flex-col" style={{ minHeight: 720 }}>
      <AgentStudioHeader />
      <section className="flex flex-col items-center gap-3 px-16 pt-6 pb-30">
        <h1 className="text-heading-large text-text-normal-normal w-full">우리 팀의 Agent</h1>
        {children}
      </section>
    </div>
  );
}

function StatefulAgentStudioList(args: AgentStudioListStoryArgs) {
  const [selectedFilter, setSelectedFilter] = useState<AgentStudioFilter>(args.selectedFilter);
  const [showMineOnly, setShowMineOnly] = useState(args.showMineOnly);
  const [agents, setAgents] = useState<readonly AgentStudioCardModel[]>(AGENT_STUDIO_MULTI_ACTIVE_LIST_FIXTURE);
  const visibleAgents = showMineOnly ? agents.filter((agent) => agent.isEditable) : agents;

  const updateStatus = (agent: AgentStudioCardModel, status: AgentStudioCardModel['status']) => {
    setAgents((current) => current.map((item) => (item.id === agent.id ? { ...item, status } : item)));
  };

  return (
    <AgentStudioListSurface>
      <div className="flex w-full items-center gap-5">
        <AgentFilterTabs
          filters={AGENT_STUDIO_FILTERS}
          selected={selectedFilter}
          showMineOnly={showMineOnly}
          onChange={(value) => {
            setSelectedFilter(value);
            args.onFilterChange(value);
          }}
          onShowMineOnlyChange={(checked) => {
            setShowMineOnly(checked);
            args.onShowMineOnlyChange(checked);
          }}
        />
        <AgentCreateButton onClick={args.onCreate} />
      </div>
      <div className="flex w-full flex-wrap items-start gap-6">
        <AgentStudioListContent
          agents={visibleAgents}
          selectedFilter={selectedFilter}
          actionDisabled={args.actionDisabled}
          onActivate={(agent) => {
            updateStatus(agent, 'active');
            args.onActivate(agent);
          }}
          onDeactivate={(agent) => {
            updateStatus(agent, 'inactive');
            args.onDeactivate(agent);
          }}
          onEdit={args.onEdit}
        />
      </div>
    </AgentStudioListSurface>
  );
}

function AgentStudioListLoadingSurface() {
  return (
    <AgentStudioListSurface>
      <div className="flex w-full items-center gap-5">
        <AgentFilterTabs
          filters={AGENT_STUDIO_FILTERS}
          selected="all"
          showMineOnly={false}
          onChange={() => undefined}
          onShowMineOnlyChange={() => undefined}
        />
        <AgentCreateButton />
      </div>
      <div className="flex w-full flex-wrap items-start gap-6">
        <AgentStudioListSkeleton selectedFilter="all" />
      </div>
    </AgentStudioListSurface>
  );
}

const meta = {
  title: 'Screens/Agent Studio/List',
  tags: ['autodocs'],
  args: {
    selectedFilter: 'all',
    showMineOnly: false,
    actionDisabled: false,
    onCreate: fn(),
    onFilterChange: fn(),
    onShowMineOnlyChange: fn(),
    onActivate: fn(),
    onDeactivate: fn(),
    onEdit: fn(),
  },
  argTypes: {
    selectedFilter: {
      control: 'inline-radio',
      options: filterOptions,
    },
    showMineOnly: {
      control: 'boolean',
    },
    actionDisabled: {
      control: 'boolean',
    },
    onCreate: { control: false },
    onFilterChange: { control: false },
    onShowMineOnlyChange: { control: false },
    onActivate: { control: false },
    onDeactivate: { control: false },
    onEdit: { control: false },
  },
  parameters: {
    msw: {
      handlers: agentStudioListHandlers,
    },
    ...catchupParameters({
      level: 'screen',
      domain: 'agent-studio',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      designSource: 'figma',
      states: ['fixture-default', 'filter-tabs', 'loading'],
      dataNotes: ['Uses AGENT_STUDIO_MULTI_ACTIVE_LIST_FIXTURE and AGENT_STUDIO_FILTERS.'],
      reuseNotes: [
        'List surface composes AgentStudioHeader, AgentFilterTabs, AgentCreateButton, and AgentStudioListContent.',
        'Loading state reuses AgentStudioListSkeleton.',
      ],
      interactionNotes: [
        'Actions log create, filter, mine-only switch, activate, deactivate, and edit events.',
      ],
    }),
  },
} satisfies Meta<AgentStudioListStoryArgs>;

export default meta;

type Story = StoryObj<AgentStudioListStoryArgs>;

export const FixtureDefault: Story = {
  parameters: {
    ...catchupParameters({
      level: 'screen',
      domain: 'agent-studio',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      figmaLab: {
        caseId: 'agent-studio-list-page',
        groupId: 'agent-studio',
      },
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/%F0%9F%8D%85-Design-System?node-id=14795-99034&m=dev',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '14795:99034',
      },
      viewport: {
        width: 1184,
        height: 720,
      },
      states: ['fixture-default', 'active-empty-after-deactivate', 'filter-tabs'],
    }),
  },
  render: (args) => <StatefulAgentStudioList key={`${args.selectedFilter}:${args.showMineOnly}`} {...args} />,
  play: async ({ args, canvasElement, step, userEvent }) => {
    const canvas = within(canvasElement);

    await step('select draft filter', async () => {
      await userEvent.click(canvas.getByRole('button', { name: '제작중' }));
      await expect(args.onFilterChange).toHaveBeenCalledWith('draft');
    });

    await step('toggle mine only', async () => {
      await userEvent.click(canvas.getByRole('switch', { name: '내 에이전트만' }));
      await expect(args.onShowMineOnlyChange).toHaveBeenCalledWith(true);
    });
  },
};

export const ListLoading: Story = {
  parameters: {
    ...catchupParameters({
      level: 'screen',
      domain: 'agent-studio',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'loading',
      figmaLab: {
        caseId: 'agent-studio-list-loading',
        groupId: 'agent-studio',
      },
      designSource: 'dev-preview',
      viewport: {
        width: 1184,
        height: 720,
      },
      states: ['loading'],
    }),
  },
  render: () => <AgentStudioListLoadingSurface />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getAllByLabelText(/로딩 섹션/)[0]).toBeInTheDocument();
  },
};
