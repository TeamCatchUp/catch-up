import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../.storybook/catchupStoryParameters';
import type { AgentStudioFilter } from '../../../types/agentStudioModel';
import AgentStudioListSkeleton from './AgentStudioListSkeleton';

interface AgentStudioListSkeletonStoryArgs {
  selectedFilter: AgentStudioFilter;
}

const filterOptions: readonly AgentStudioFilter[] = ['all', 'active', 'draft', 'inactive'];

const meta = {
  title: 'Compositions/Agent Studio/List/AgentStudioListSkeleton',
  component: AgentStudioListSkeleton,
  tags: ['autodocs'],
  args: {
    selectedFilter: 'all',
  },
  argTypes: {
    selectedFilter: {
      control: 'inline-radio',
      options: filterOptions,
    },
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'agent-studio',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'loading',
      designSource: 'dev-preview',
      states: ['grouped-loading', 'filtered-grid-loading'],
      reuseNotes: ['List screen loading state delegates to this composition.'],
    }),
  },
} satisfies Meta<AgentStudioListSkeletonStoryArgs>;

export default meta;

type Story = StoryObj<AgentStudioListSkeletonStoryArgs>;

export const Playground: Story = {
  render: (args) => (
    <div className="bg-fill-normal-normal flex min-h-96 flex-wrap items-start gap-6 p-6">
      <AgentStudioListSkeleton {...args} />
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getAllByLabelText('Agent 카드 로딩')[0]).toBeInTheDocument();
  },
};

export const FilteredGrid: Story = {
  args: {
    selectedFilter: 'active',
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'agent-studio',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'loading',
      designSource: 'dev-preview',
      states: ['filtered-grid-loading'],
    }),
  },
  render: (args) => (
    <div className="bg-fill-normal-normal flex min-h-96 flex-wrap items-start gap-6 p-6">
      <AgentStudioListSkeleton {...args} />
    </div>
  ),
};
