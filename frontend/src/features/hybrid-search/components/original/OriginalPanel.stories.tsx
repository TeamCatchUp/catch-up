'use client';

import type { Meta, StoryObj } from '@storybook/nextjs-vite';

import {
  emptyConversationResponse,
  fullConversationResponse,
} from '@/features/hybrid-search/components/original/__fixtures__/originalContent.fixtures';
import ChannelTalkOriginalPanelContent from '@/features/hybrid-search/components/original/channel-talk/ChannelTalkOriginalPanelContent';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import OriginalPanel from './OriginalPanel';
import { Case, PanelFrame, StorySurface } from './OriginalPanelStoryFrame';

const meta = {
  title: 'Compositions/Hybrid Search/Original Panel',
  tags: ['autodocs'],
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'hybrid-search',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      figmaLab: {
        caseId: 'original-panel',
        groupId: 'original-panel',
      },
      designSource: 'dev-preview',
      states: ['channel-talk-panel', 'container-coming-soon', 'container-empty'],
      dataNotes: [
        'This story now keeps only assembled ChannelTalk panel and OriginalPanel container states.',
        'Leaf content, timeline, metadata, panel-state, and Slack coverage live in dedicated Original Panel child stories.',
      ],
      reuseNotes: [
        'ChannelTalk assembled stories render the production full panel content component.',
        'Container states render the production OriginalPanel query/container boundary with disabled query states.',
      ],
    }),
  },
} satisfies Meta;

export default meta;

type Story = StoryObj;

export const ChannelTalkPanels: Story = {
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'hybrid-search',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      figmaLab: {
        caseId: 'panel-content',
        groupId: 'original-panel',
      },
      designSource: 'dev-preview',
      states: ['panel-content', 'empty-conversation'],
    }),
  },
  render: () => (
    <StorySurface>
      <Case label="현실적인 전체 대화">
        <PanelFrame>
          <ChannelTalkOriginalPanelContent data={fullConversationResponse} />
        </PanelFrame>
      </Case>
      <Case label="메시지 0건">
        <PanelFrame>
          <ChannelTalkOriginalPanelContent data={emptyConversationResponse} />
        </PanelFrame>
      </Case>
    </StorySurface>
  ),
};

export const ContainerStates: Story = {
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'hybrid-search',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'empty',
      figmaLab: {
        caseId: 'panel',
        groupId: 'original-panel',
      },
      designSource: 'dev-preview',
      states: ['coming-soon-container', 'empty-container'],
    }),
  },
  render: () => (
    <StorySurface>
      <Case label="ComingSoon connector=jira">
        <PanelFrame>
          <OriginalPanel connector="jira" entityType="issue" documentId="jira:issue:1" />
        </PanelFrame>
      </Case>
      <Case label="Empty documentId=null">
        <PanelFrame>
          <OriginalPanel connector="channel_talk" entityType="user_chat" documentId={null} />
        </PanelFrame>
      </Case>
    </StorySurface>
  ),
};
