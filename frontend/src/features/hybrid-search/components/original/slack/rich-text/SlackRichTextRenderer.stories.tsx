'use client';

import type { Meta, StoryObj } from '@storybook/nextjs-vite';

import { slackOriginalThreadResponse } from '@/features/hybrid-search/components/original/__fixtures__/slackOriginal.fixtures';
import { parseSlackOriginalThread } from '@/features/hybrid-search/utils/slack-original/parseSlackOriginal';

import { catchupParameters } from '../../../../../../../.storybook/catchupStoryParameters';
import { Case, SlackPanelWidth, StorySurface } from '../../OriginalPanelStoryFrame';
import SlackRichTextRenderer from './SlackRichTextRenderer';

const thread = parseSlackOriginalThread(slackOriginalThreadResponse);
const richMessage = thread.messages[1];

const meta = {
  title: 'Compositions/Hybrid Search/Original/SlackRichTextRenderer',
  tags: ['autodocs'],
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'hybrid-search',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      figmaLab: {
        caseId: 'slack-rich-message',
        groupId: 'original-panel',
      },
      designSource: 'figma',
      states: ['inline-code', 'bold', 'strike', 'link', 'bullet-list', 'ordered-list', 'quote', 'code-block'],
      viewport: {
        width: 520,
        height: 680,
      },
      dataNotes: ['Uses the Slack rich-text fixture after parser normalization.'],
      reuseNotes: ['Covers the rich-text renderer before it is embedded in SlackMessageItem.'],
    }),
  },
} satisfies Meta;

export default meta;

type Story = StoryObj;

export const RichBlocks: Story = {
  render: () => (
    <StorySurface>
      <Case label="Slack rich text blocks">
        <SlackPanelWidth>
          <SlackRichTextRenderer blocks={richMessage.blocks} />
        </SlackPanelWidth>
      </Case>
    </StorySurface>
  ),
};

export const EmptyBlocks: Story = {
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'hybrid-search',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'empty',
      designSource: 'dev-preview',
      states: ['empty-rich-text'],
    }),
  },
  render: () => (
    <StorySurface>
      <Case label="empty blocks">
        <SlackPanelWidth>
          <SlackRichTextRenderer blocks={[]} />
        </SlackPanelWidth>
      </Case>
    </StorySurface>
  ),
};
