'use client';

import type { Meta, StoryObj } from '@storybook/nextjs-vite';

import { slackOriginalThreadResponse } from '@/features/hybrid-search/components/original/__fixtures__/slackOriginal.fixtures';
import SlackOriginalPanelContent from '@/features/hybrid-search/components/original/slack/SlackOriginalPanelContent';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import { Case, SlackPanelFrame, StorySurface } from './OriginalPanelStoryFrame';

const meta = {
  title: 'Compositions/Hybrid Search/Original/SlackOriginalPanel',
  tags: ['autodocs'],
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
      states: ['slack-full-panel', 'slack-pagination-sentinel'],
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/%F0%9F%8D%85-Design-System?node-id=14152-56488&m=dev',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '14152:56488',
      },
      viewport: {
        width: 520,
        height: 760,
      },
      dataNotes: ['Uses the Slack original-thread response fixture and production Slack parser.'],
      reuseNotes: [
        'Keeps the assembled Slack original panel story separate from header, message, rich-text, and attachment stories.',
      ],
    }),
  },
} satisfies Meta;

export default meta;

type Story = StoryObj;

export const FullPanel: Story = {
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
