'use client';

import type { Meta, StoryObj } from '@storybook/nextjs-vite';

import { messageItemVariants } from '@/features/hybrid-search/components/original/__fixtures__/originalContent.fixtures';
import MessageItem from '@/features/hybrid-search/components/original/channel-talk/timeline/MessageItem';
import DateIndicator from '@/features/hybrid-search/components/original/shared/DateIndicator';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import { Case, CHANNEL_TALK_STORY_DOCUMENT_ID, PanelWidth, StorySurface } from './OriginalPanelStoryFrame';

const meta = {
  title: 'Compositions/Hybrid Search/Original Panel/ChannelTalkTimeline',
  tags: ['autodocs'],
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'hybrid-search',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      figmaLab: {
        caseId: 'message-item',
        groupId: 'original-panel',
      },
      designSource: 'dev-preview',
      states: ['message-item', 'date-indicator'],
      dataNotes: ['Uses realistic ChannelTalk timeline message variants from original-panel fixtures.'],
      reuseNotes: ['Renders production DateIndicator and MessageItem components.'],
    }),
  },
} satisfies Meta;

export default meta;

type Story = StoryObj;

export const MessageVariants: Story = {
  render: () => (
    <StorySurface>
      <Case label="날짜 구분선">
        <PanelWidth>
          <DateIndicator date="2026-05-20T09:30:00+09:00" />
        </PanelWidth>
      </Case>
      {messageItemVariants.map((variant) => (
        <Case key={variant.item.id} label={variant.label}>
          <PanelWidth>
            <MessageItem
              item={variant.item}
              connector="channel_talk"
              documentId={CHANNEL_TALK_STORY_DOCUMENT_ID}
            />
          </PanelWidth>
        </Case>
      ))}
    </StorySurface>
  ),
};
