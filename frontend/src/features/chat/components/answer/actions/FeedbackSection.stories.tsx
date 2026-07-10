'use client';

import { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, waitFor, within } from 'storybook/test';

import {
  chatStoryHistoryId,
  chatStoryMessageId,
  chatStorySessionId,
} from '@/features/chat/__fixtures__/chatStory.fixtures';
import { chatActionHandlers, chatFeedbackErrorHandler } from '@/features/chat/__fixtures__/chatStory.handlers';

import { catchupParameters } from '../../../../../../.storybook/catchupStoryParameters';
import FeedbackSection from './FeedbackSection';

interface FeedbackSectionStoryArgs {
  visible: boolean;
  onFeedbackSubmitted: (messageId: string, isLiked: boolean | undefined) => void;
}

function FeedbackSectionSurface(args: FeedbackSectionStoryArgs) {
  const [feedbackVisibleMap, setFeedbackVisibleMap] = useState<Record<string, boolean>>({
    [chatStoryMessageId]: args.visible,
  });

  return (
    <div className="bg-fill-normal-normal flex min-h-96 items-start justify-center p-6">
      <FeedbackSection
        messageId={chatStoryMessageId}
        sessionId={chatStorySessionId}
        chatHistoryId={chatStoryHistoryId}
        feedbackVisibleMap={feedbackVisibleMap}
        setFeedbackVisibleMap={setFeedbackVisibleMap}
        onFeedbackSubmitted={args.onFeedbackSubmitted}
      />
    </div>
  );
}

const meta = {
  title: 'Compositions/Chat/Feedback/FeedbackSection',
  component: FeedbackSection,
  tags: ['autodocs'],
  args: {
    visible: true,
    onFeedbackSubmitted: fn(),
  },
  argTypes: {
    visible: { control: 'boolean' },
    onFeedbackSubmitted: { control: false },
  },
  parameters: {
    msw: { handlers: chatActionHandlers },
    ...catchupParameters({
      level: 'composition',
      domain: 'chat',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'msw',
      designSource: 'dev-preview',
      states: ['reason-list', 'detail-input', 'submitting', 'error', 'closed'],
      usedBy: ['chat'],
      interactionNotes: ['Interactions submit a predefined reason and a free-form detail through MSW.'],
    }),
  },
} satisfies Meta<FeedbackSectionStoryArgs>;

export default meta;

type Story = StoryObj<FeedbackSectionStoryArgs>;

export const Playground: Story = {
  render: (args) => <FeedbackSectionSurface {...args} />,
};

export const SubmitReason: Story = {
  render: (args) => <FeedbackSectionSurface {...args} />,
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);

    await userEvent.click(await canvas.findByRole('button', { name: '최신 내용이 반영되지 않았어요' }));

    await waitFor(() => expect(args.onFeedbackSubmitted).toHaveBeenCalledWith(chatStoryMessageId, false));
  },
};

export const SubmitDetail: Story = {
  render: (args) => <FeedbackSectionSurface {...args} />,
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);

    await userEvent.click(await canvas.findByRole('button', { name: '더 자세히...' }));
    await userEvent.type(
      await canvas.findByPlaceholderText('자세한 피드백을 남겨주세요.'),
      '예외 코드별 재시도 간격을 표에 추가해주세요.',
    );
    await userEvent.click(canvas.getByRole('button', { name: '제출' }));

    await waitFor(() => expect(args.onFeedbackSubmitted).toHaveBeenCalledWith(chatStoryMessageId, false));
  },
};

export const SubmissionError: Story = {
  parameters: {
    msw: { handlers: [chatFeedbackErrorHandler] },
  },
  render: (args) => <FeedbackSectionSurface {...args} />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await userEvent.click(await canvas.findByRole('button', { name: '중요한 정보가 누락되었어요' }));

    const errorMessage = await canvas.findByText('피드백 제출에 실패했습니다. 다시 시도해주세요.');
    await waitFor(() => expect(errorMessage).toBeVisible());
  },
};
