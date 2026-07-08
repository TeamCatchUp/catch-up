'use client';

import type { Meta, StoryObj } from '@storybook/nextjs-vite';

import { slackOriginalThreadResponse } from '@/features/hybrid-search/components/original/__fixtures__/slackOriginal.fixtures';
import { parseSlackOriginalThread } from '@/features/hybrid-search/utils/slack-original/parseSlackOriginal';

import { catchupParameters } from '../../../../../../../.storybook/catchupStoryParameters';
import { Case, SlackPanelWidth, StorySurface } from '../../OriginalPanelStoryFrame';
import SlackThreadHeader from './SlackThreadHeader';

interface SlackThreadHeaderStoryArgs {
  channelName: string;
  participantNames: string[];
}

const thread = parseSlackOriginalThread(slackOriginalThreadResponse);

const meta = {
  title: 'Compositions/Hybrid Search/Original/SlackThreadHeader',
  tags: ['autodocs'],
  args: {
    channelName: thread.channelName,
    participantNames: thread.participantNames,
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'hybrid-search',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      figmaLab: {
        caseId: 'slack-thread-header',
        groupId: 'original-panel',
      },
      designSource: 'figma',
      states: ['channel-name', 'participants', 'empty-participants', 'long-text-truncation'],
      viewport: {
        width: 520,
        height: 360,
      },
      dataNotes: ['Uses the parsed Slack original-thread fixture to keep channel and participant labels realistic.'],
      reuseNotes: ['Covers SlackThreadHeader independently from the assembled original panel.'],
    }),
  },
} satisfies Meta<SlackThreadHeaderStoryArgs>;

export default meta;

type Story = StoryObj<SlackThreadHeaderStoryArgs>;

export const Default: Story = {
  render: (args) => (
    <StorySurface>
      <Case label="기본 헤더">
        <SlackPanelWidth>
          <SlackThreadHeader {...args} />
        </SlackPanelWidth>
      </Case>
    </StorySurface>
  ),
};

export const EmptyParticipants: Story = {
  args: {
    participantNames: [],
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'hybrid-search',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'empty',
      designSource: 'dev-preview',
      states: ['empty-participants'],
    }),
  },
  render: (args) => (
    <StorySurface>
      <Case label="참여자 없음">
        <SlackPanelWidth>
          <SlackThreadHeader {...args} />
        </SlackPanelWidth>
      </Case>
    </StorySurface>
  ),
};
