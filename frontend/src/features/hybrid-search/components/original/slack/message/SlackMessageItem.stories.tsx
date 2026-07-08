'use client';

import type { Meta, StoryObj } from '@storybook/nextjs-vite';

import { slackOriginalThreadResponse } from '@/features/hybrid-search/components/original/__fixtures__/slackOriginal.fixtures';
import { parseSlackOriginalThread } from '@/features/hybrid-search/utils/slack-original/parseSlackOriginal';

import { catchupParameters } from '../../../../../../../.storybook/catchupStoryParameters';
import { Case, SlackPanelWidth, StorySurface } from '../../OriginalPanelStoryFrame';
import SlackMessageItem from './SlackMessageItem';

type SlackMessagePreset = 'user-question' | 'bot-rich' | 'reply-file';

interface SlackMessageItemStoryArgs {
  preset: SlackMessagePreset;
  originalUrl: string | null;
}

const thread = parseSlackOriginalThread(slackOriginalThreadResponse);
const messageFixtures = {
  'user-question': thread.messages[0],
  'bot-rich': thread.messages[1],
  'reply-file': thread.messages[2],
} as const;
const presetOptions: readonly SlackMessagePreset[] = ['user-question', 'bot-rich', 'reply-file'];

function SlackMessageItemSurface(args: SlackMessageItemStoryArgs) {
  const message = messageFixtures[args.preset];

  return (
    <StorySurface>
      <Case label={args.preset}>
        <SlackPanelWidth>
          <SlackMessageItem message={message} originalUrl={args.originalUrl} />
        </SlackPanelWidth>
      </Case>
    </StorySurface>
  );
}

const meta = {
  title: 'Compositions/Hybrid Search/Original/SlackMessageItem',
  tags: ['autodocs'],
  args: {
    preset: 'bot-rich',
    originalUrl: thread.url,
  },
  argTypes: {
    preset: {
      control: 'select',
      options: presetOptions,
    },
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'hybrid-search',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      figmaLab: {
        caseId: 'slack-message-item',
        groupId: 'original-panel',
      },
      designSource: 'figma',
      states: ['user-message', 'bot-rich-message', 'edited-label', 'file-attachment', 'link-preview'],
      viewport: {
        width: 520,
        height: 680,
      },
      dataNotes: ['Uses parsed Slack message fixtures with rich text, files, link preview, and reply states.'],
      reuseNotes: ['Covers SlackMessageItem independently from the assembled Slack original panel.'],
    }),
  },
} satisfies Meta<SlackMessageItemStoryArgs>;

export default meta;

type Story = StoryObj<SlackMessageItemStoryArgs>;

export const Default: Story = {
  render: (args) => <SlackMessageItemSurface {...args} />,
};

export const UserQuestion: Story = {
  args: {
    preset: 'user-question',
  },
  render: (args) => <SlackMessageItemSurface {...args} />,
};

export const ReplyWithFile: Story = {
  args: {
    preset: 'reply-file',
  },
  render: (args) => <SlackMessageItemSurface {...args} />,
};
