import type { Meta, StoryObj } from '@storybook/nextjs-vite';

import { catchupParameters } from '../../../../../../.storybook/catchupStoryParameters';
import SourceBadge, { type SourceType } from './SourceBadge';

interface SourceBadgeStoryArgs {
  sourceType: SourceType;
  n: string;
}

const sourceTypeOptions: readonly SourceType[] = ['jira', 'github', 'slack', 'confluence', 'channel_talk'];

const meta = {
  title: 'Primitives/Chat/Answers/SourceBadge',
  component: SourceBadge,
  tags: ['autodocs'],
  args: {
    sourceType: 'slack',
    n: '1',
  },
  argTypes: {
    sourceType: {
      control: 'select',
      options: sourceTypeOptions,
    },
    n: {
      control: 'text',
    },
  },
  parameters: {
    ...catchupParameters({
      level: 'primitive',
      domain: 'chat',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'dev-preview',
      states: ['source-variant', 'citation-order'],
      usedBy: ['chat'],
      reuseNotes: ['Inline citation badge used by rendered RAG answers.'],
      interactionNotes: ['Controls switch the integration logo and displayed citation order.'],
    }),
  },
  render: (args) => (
    <div className="bg-fill-normal-normal flex min-h-32 items-center justify-center p-6">
      <SourceBadge {...args} />
    </div>
  ),
} satisfies Meta<SourceBadgeStoryArgs>;

export default meta;

type Story = StoryObj<SourceBadgeStoryArgs>;

export const Playground: Story = {};

export const SourceVariants: Story = {
  render: () => (
    <div className="bg-fill-normal-normal flex min-h-32 flex-wrap items-center justify-center gap-3 p-6">
      {sourceTypeOptions.map((sourceType, index) => (
        <SourceBadge key={sourceType} sourceType={sourceType} n={String(index + 1)} />
      ))}
    </div>
  ),
};
