import type { Meta, StoryObj } from '@storybook/nextjs-vite';

import {
  chatSourceFixtures,
  type ChatSourcePreset,
  chatSourcePresetOptions,
} from '@/features/chat/__fixtures__/chatStory.fixtures';

import { catchupParameters } from '../../../../../../.storybook/catchupStoryParameters';
import SourceCard from './SourceCard';

interface SourceCardStoryArgs {
  sourcePreset: ChatSourcePreset;
  showCount: boolean;
  count: number;
}

function SourceCardSurface(args: SourceCardStoryArgs) {
  return (
    <div className="bg-fill-normal-normal flex min-h-72 items-start justify-center p-6">
      <div className="w-96 max-w-full">
        <SourceCard source={chatSourceFixtures[args.sourcePreset]} showCount={args.showCount} count={args.count} />
      </div>
    </div>
  );
}

const meta = {
  title: 'Compositions/Chat/Sources/SourceCard',
  component: SourceCard,
  tags: ['autodocs'],
  args: {
    sourcePreset: 'jira',
    showCount: true,
    count: 1,
  },
  argTypes: {
    sourcePreset: {
      control: 'select',
      options: chatSourcePresetOptions,
    },
    showCount: {
      control: 'boolean',
    },
    count: {
      control: { type: 'number', min: 0 },
    },
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'chat',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      designSource: 'dev-preview',
      states: ['source-variant', 'cited', 'recommended', 'metadata-fallback'],
      usedBy: ['chat'],
      dataNotes: ['Fixtures cover Jira, GitHub, Slack, Confluence, and two ChannelTalk entity types.'],
      interactionNotes: ['Controls expose source variants and citation-count visibility.'],
    }),
  },
} satisfies Meta<SourceCardStoryArgs>;

export default meta;

type Story = StoryObj<SourceCardStoryArgs>;

export const Playground: Story = {
  render: (args) => <SourceCardSurface {...args} />,
};

export const SourceVariants: Story = {
  render: (args) => (
    <div className="bg-fill-normal-normal grid min-h-180 grid-cols-1 gap-10 p-8 lg:grid-cols-2">
      {chatSourcePresetOptions.map((preset, index) => (
        <SourceCard
          key={preset}
          source={chatSourceFixtures[preset]}
          showCount={chatSourceFixtures[preset].is_cited && args.showCount}
          count={index + 1}
        />
      ))}
    </div>
  ),
};

export const MissingMetadata: Story = {
  render: (args) => (
    <div className="bg-fill-normal-normal flex min-h-72 items-start justify-center p-6">
      <div className="w-96 max-w-full">
        <SourceCard
          source={{
            ...chatSourceFixtures.jira,
            id: 'chat-source-missing-metadata',
            repo: '',
            title: '',
            author: '',
            date: '',
            html_url: '',
          }}
          showCount={args.showCount}
          count={args.count}
        />
      </div>
    </div>
  ),
};
