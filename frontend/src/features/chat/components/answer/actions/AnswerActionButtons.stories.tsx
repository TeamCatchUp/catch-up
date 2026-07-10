'use client';

import { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, waitFor, within } from 'storybook/test';

import {
  chatAnswerWithCitations,
  chatStoryHistoryId,
  chatStoryMessageId,
  chatStorySessionId,
} from '@/features/chat/__fixtures__/chatStory.fixtures';
import { chatActionHandlers } from '@/features/chat/__fixtures__/chatStory.handlers';
import type { IconItem } from '@/features/chat/types/props/actionProps';
import Bookmark from '@/public/icons/icon/bookmark.svg';
import BookmarkFilled from '@/public/icons/icon/bookmark_filled.svg';
import Copy from '@/public/icons/icon/copy.svg';
import Rotate from '@/public/icons/icon/rotate.svg';
import ThumbsDown from '@/public/icons/icon/thumbs-down.svg';
import ThumbsDownFilled from '@/public/icons/icon/thumbs-down_filled.svg';
import ThumbsUp from '@/public/icons/icon/thumbs-up.svg';
import ThumbsUpFilled from '@/public/icons/icon/thumbs-up_filled.svg';

import { catchupParameters } from '../../../../../../.storybook/catchupStoryParameters';
import AnswerActionButtons from './AnswerActionButtons';

type FeedbackState = 'unrated' | 'liked' | 'disliked';

interface AnswerActionButtonsStoryArgs {
  feedbackState: FeedbackState;
  saved: boolean;
  onRetry: () => void;
  onFeedbackSubmitted: (messageId: string, isLiked: boolean | undefined) => void;
}

const feedbackStateOptions: readonly FeedbackState[] = ['unrated', 'liked', 'disliked'];
const answerIcons: IconItem[] = [
  { name: 'Copy', icon: Copy },
  { name: 'Bookmark', icon: Bookmark, activeIcon: BookmarkFilled },
  { name: 'ThumbsUp', icon: ThumbsUp, activeIcon: ThumbsUpFilled },
  { name: 'ThumbsDown', icon: ThumbsDown, activeIcon: ThumbsDownFilled },
  { name: 'Rotate', icon: Rotate },
];

function AnswerActionButtonsSurface(args: AnswerActionButtonsStoryArgs) {
  const [feedbackVisibleMap, setFeedbackVisibleMap] = useState<Record<string, boolean>>({});
  const isLiked = args.feedbackState === 'liked' ? true : args.feedbackState === 'disliked' ? false : undefined;

  return (
    <div className="bg-fill-normal-normal flex min-h-32 items-start justify-center p-6">
      <AnswerActionButtons
        icons={answerIcons}
        messageId={chatStoryMessageId}
        answerContent={chatAnswerWithCitations}
        sessionId={chatStorySessionId}
        chatHistoryId={chatStoryHistoryId}
        isLiked={isLiked}
        isSaved={args.saved}
        feedbackVisibleMap={feedbackVisibleMap}
        setFeedbackVisibleMap={setFeedbackVisibleMap}
        onRetry={args.onRetry}
        onFeedbackSubmitted={args.onFeedbackSubmitted}
      />
    </div>
  );
}

const meta = {
  title: 'Compositions/Chat/Answers/AnswerActionButtons',
  component: AnswerActionButtons,
  tags: ['autodocs'],
  args: {
    feedbackState: 'unrated',
    saved: false,
    onRetry: fn(),
    onFeedbackSubmitted: fn(),
  },
  argTypes: {
    feedbackState: { control: 'select', options: feedbackStateOptions },
    saved: { control: 'boolean' },
    onRetry: { control: false },
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
      states: ['unrated', 'liked', 'disliked', 'saved', 'feedback-panel-open'],
      usedBy: ['chat'],
      interactionNotes: ['Actions cover save, like, dislike-panel toggle, and retry callbacks.'],
    }),
  },
} satisfies Meta<AnswerActionButtonsStoryArgs>;

export default meta;

type Story = StoryObj<AnswerActionButtonsStoryArgs>;

export const Playground: Story = {
  render: (args) => <AnswerActionButtonsSurface {...args} />,
};

export const ActionInteraction: Story = {
  render: (args) => <AnswerActionButtonsSurface {...args} />,
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);
    const saveButton = canvas.getByRole('button', { name: '저장하기' });
    const likeButton = canvas.getByRole('button', { name: '좋은 응답' });

    await userEvent.click(saveButton);
    await expect(saveButton).toHaveAttribute('aria-pressed', 'true');

    await userEvent.click(likeButton);
    await waitFor(() => expect(args.onFeedbackSubmitted).toHaveBeenCalledWith(chatStoryMessageId, true));

    await userEvent.click(canvas.getByRole('button', { name: '다시 시도하기' }));
    await expect(args.onRetry).toHaveBeenCalledOnce();
  },
};

export const DislikePanelToggle: Story = {
  render: (args) => <AnswerActionButtonsSurface {...args} />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const dislikeButton = canvas.getByRole('button', { name: '별로인 응답' });

    await userEvent.click(dislikeButton);

    await expect(dislikeButton).toHaveAttribute('aria-pressed', 'true');
  },
};
