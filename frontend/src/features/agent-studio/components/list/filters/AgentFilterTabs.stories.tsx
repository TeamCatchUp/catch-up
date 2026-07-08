'use client';

import { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../.storybook/catchupStoryParameters';
import { AGENT_STUDIO_FILTERS } from '../../../fixtures/agentStudioFixtures';
import type { AgentStudioFilter } from '../../../types/agentStudioModel';
import AgentFilterTabs from './AgentFilterTabs';

interface AgentFilterTabsStoryArgs {
  selected: AgentStudioFilter;
  showMineOnly: boolean;
  onChange: (value: AgentStudioFilter) => void;
  onShowMineOnlyChange: (checked: boolean) => void;
}

const filterOptions: readonly AgentStudioFilter[] = ['all', 'active', 'draft', 'inactive'];

function StatefulAgentFilterTabs(args: AgentFilterTabsStoryArgs) {
  const [selected, setSelected] = useState(args.selected);
  const [showMineOnly, setShowMineOnly] = useState(args.showMineOnly);

  return (
    <div className="bg-fill-normal-normal flex min-h-28 items-start p-6">
      <AgentFilterTabs
        filters={AGENT_STUDIO_FILTERS}
        selected={selected}
        showMineOnly={showMineOnly}
        onChange={(value) => {
          setSelected(value);
          args.onChange(value);
        }}
        onShowMineOnlyChange={(checked) => {
          setShowMineOnly(checked);
          args.onShowMineOnlyChange(checked);
        }}
      />
    </div>
  );
}

const meta = {
  title: 'Compositions/Agent Studio/List/AgentFilterTabs',
  tags: ['autodocs'],
  args: {
    selected: 'all',
    showMineOnly: false,
    onChange: fn(),
    onShowMineOnlyChange: fn(),
  },
  argTypes: {
    selected: {
      control: 'inline-radio',
      options: filterOptions,
    },
    showMineOnly: {
      control: 'boolean',
    },
    onChange: {
      control: false,
    },
    onShowMineOnlyChange: {
      control: false,
    },
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'agent-studio',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'figma',
      states: ['all', 'active', 'draft', 'inactive', 'mine-only'],
      reuseNotes: ['Feature-specific filter rail composed from shared Chip and Switch primitives.'],
      interactionNotes: ['The play function selects a status chip and toggles the mine-only switch.'],
    }),
  },
} satisfies Meta<AgentFilterTabsStoryArgs>;

export default meta;

type Story = StoryObj<AgentFilterTabsStoryArgs>;

export const Playground: Story = {
  render: (args) => <StatefulAgentFilterTabs key={`${args.selected}:${args.showMineOnly}`} {...args} />,
  play: async ({ args, canvasElement, step, userEvent }) => {
    const canvas = within(canvasElement);

    await step('select inactive filter', async () => {
      await userEvent.click(canvas.getByRole('button', { name: '사용 안함' }));
      await expect(args.onChange).toHaveBeenCalledWith('inactive');
    });

    await step('toggle mine only', async () => {
      await userEvent.click(canvas.getByRole('switch', { name: '내 에이전트만' }));
      await expect(args.onShowMineOnlyChange).toHaveBeenCalledWith(true);
    });
  },
};
