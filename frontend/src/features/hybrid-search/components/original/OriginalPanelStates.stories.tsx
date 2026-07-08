'use client';

import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import OriginalPanelComingSoon from '@/features/hybrid-search/components/original/shared/states/OriginalPanelComingSoon';
import OriginalPanelEmpty from '@/features/hybrid-search/components/original/shared/states/OriginalPanelEmpty';
import OriginalPanelError from '@/features/hybrid-search/components/original/shared/states/OriginalPanelError';
import OriginalPanelSkeleton from '@/features/hybrid-search/components/original/shared/states/OriginalPanelSkeleton';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import { Case, PanelFrame, StorySurface } from './OriginalPanelStoryFrame';

interface OriginalPanelStatesStoryArgs {
  onRetry: () => void;
}

const meta = {
  title: 'Compositions/Hybrid Search/Original Panel/States',
  tags: ['autodocs'],
  args: {
    onRetry: fn(),
  },
  argTypes: {
    onRetry: {
      control: false,
    },
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'hybrid-search',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'loading',
      figmaLab: {
        caseId: 'panel-skeleton',
        groupId: 'original-panel',
      },
      designSource: 'dev-preview',
      states: ['panel-skeleton', 'panel-empty', 'panel-error', 'panel-coming-soon'],
      reuseNotes: ['Renders shared original-panel state components independently from the data container.'],
      interactionNotes: ['Actions log retry clicks from OriginalPanelError variants.'],
    }),
  },
} satisfies Meta<OriginalPanelStatesStoryArgs>;

export default meta;

type Story = StoryObj<OriginalPanelStatesStoryArgs>;

export const AllStates: Story = {
  render: ({ onRetry }) => (
    <StorySurface>
      <Case label="로딩 중">
        <PanelFrame>
          <OriginalPanelSkeleton />
        </PanelFrame>
      </Case>
      <Case label="선택된 문서 없음">
        <PanelFrame>
          <OriginalPanelEmpty />
        </PanelFrame>
      </Case>
      <Case label="400 지원하지 않는 원문 유형">
        <PanelFrame>
          <OriginalPanelError message="지원하지 않는 원문 유형입니다" onRetry={onRetry} />
        </PanelFrame>
      </Case>
      <Case label="404 연동 정보 없음">
        <PanelFrame>
          <OriginalPanelError message="원문을 불러올 수 없어요 (연동 정보 없음)" onRetry={onRetry} />
        </PanelFrame>
      </Case>
      <Case label="422 제공처 오류">
        <PanelFrame>
          <OriginalPanelError message="원문 제공처에서 오류가 발생했어요" onRetry={onRetry} />
        </PanelFrame>
      </Case>
      {['Jira', 'Github', 'Slack', '컨플루언스 위키 문서', '채널톡 도큐먼트'].map((toolName) => (
        <Case key={toolName} label={`준비 중 ${toolName}`}>
          <PanelFrame>
            <OriginalPanelComingSoon toolName={toolName} />
          </PanelFrame>
        </Case>
      ))}
    </StorySurface>
  ),
  play: async ({ args, canvasElement, userEvent }) => {
    const canvas = within(canvasElement);
    await userEvent.click(canvas.getAllByRole('button', { name: '다시 시도' })[0]);
    await expect(args.onRetry).toHaveBeenCalled();
  },
};
