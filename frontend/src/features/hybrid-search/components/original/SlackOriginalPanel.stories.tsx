'use client';

import type { Meta, StoryObj } from '@storybook/nextjs-vite';

import { slackOriginalThreadResponse } from '@/features/hybrid-search/components/original/__fixtures__/slackOriginal.fixtures';
import SlackThreadHeader from '@/features/hybrid-search/components/original/slack/header/SlackThreadHeader';
import SlackMessageItem from '@/features/hybrid-search/components/original/slack/message/SlackMessageItem';
import SlackOriginalPanelContent from '@/features/hybrid-search/components/original/slack/SlackOriginalPanelContent';
import { parseSlackOriginalThread } from '@/features/hybrid-search/utils/slack-original/parseSlackOriginal';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import { Case, SlackPanelFrame, SlackPanelWidth, StorySurface } from './OriginalPanelStoryFrame';

const meta = {
  title: 'Compositions/Hybrid Search/Original Panel/Slack',
  tags: ['autodocs'],
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
      states: ['slack-thread-header', 'slack-message-item', 'slack-rich-message', 'slack-full-panel'],
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/%F0%9F%8D%85-Design-System?node-id=14427-58787&m=dev',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '14427:58787',
      },
      viewport: {
        width: 520,
        height: 760,
      },
      dataNotes: ['Uses the Slack original-thread response fixture and production Slack parser.'],
      reuseNotes: ['Renders Slack header, message item, rich message, and full panel content components.'],
    }),
  },
} satisfies Meta;

export default meta;

type Story = StoryObj;

export const MessageParts: Story = {
  render: () => {
    const thread = parseSlackOriginalThread(slackOriginalThreadResponse);

    return (
      <StorySurface>
        <Case label="Slack header">
          <SlackPanelWidth>
            <SlackThreadHeader channelName={thread.channelName} participantNames={thread.participantNames} />
          </SlackPanelWidth>
        </Case>
        <Case label="일반 메시지">
          <SlackPanelWidth>
            <SlackMessageItem message={thread.messages[0]} />
          </SlackPanelWidth>
        </Case>
        <Case label="봇 rich 메시지">
          <SlackPanelWidth>
            <SlackMessageItem message={thread.messages[1]} />
          </SlackPanelWidth>
        </Case>
      </StorySurface>
    );
  },
};

export const FullPanel: Story = {
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'hybrid-search',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      figmaLab: {
        caseId: 'slack-panel-preview',
        groupId: 'original-panel',
      },
      designSource: 'figma',
      states: ['slack-panel-preview'],
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/%F0%9F%8D%85-Design-System?node-id=14152-56488&m=dev',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '14152:56488',
      },
      viewport: {
        width: 520,
        height: 760,
      },
    }),
  },
  render: () => (
    <StorySurface>
      <Case label="Slack full panel">
        <SlackPanelFrame>
          <SlackOriginalPanelContent
            pages={[slackOriginalThreadResponse]}
            hasNextPage={false}
            isFetchingNextPage={false}
            onLoadNextPage={() => undefined}
          />
        </SlackPanelFrame>
      </Case>
    </StorySurface>
  ),
};
