'use client';

import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, waitFor, within } from 'storybook/test';

import { makeChatQAPair } from '@/features/chat/__fixtures__/chatStory.fixtures';
import { chatActionHandlers } from '@/features/chat/__fixtures__/chatStory.handlers';
import type { PipelineQueryType } from '@/features/chat/types';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import RagAnswer from './RagAnswer';

type RagAnswerState = 'resolved' | 'loading' | 'inline-error' | 'request-error';
type FeedbackState = 'unrated' | 'liked' | 'disliked';

interface RagAnswerStoryArgs {
  state: RagAnswerState;
  feedbackState: FeedbackState;
  saved: boolean;
  pipelineQueryType: PipelineQueryType;
  pipelineReasoning: string;
  onRetry: (questionId: string, questionContent: string) => void;
  onFeedbackSubmitted: (messageId: string, isLiked: boolean | undefined) => void;
}

const stateOptions: readonly RagAnswerState[] = ['resolved', 'loading', 'inline-error', 'request-error'];
const feedbackStateOptions: readonly FeedbackState[] = ['unrated', 'liked', 'disliked'];
const pipelineOptions: readonly PipelineQueryType[] = ['simple', 'standard', 'complex'];

function RagAnswerSurface(args: RagAnswerStoryArgs) {
  const isLiked = args.feedbackState === 'liked' ? true : args.feedbackState === 'disliked' ? false : undefined;
  const hasFeedback = args.feedbackState !== 'unrated';
  const emptyAnswerPair = makeChatQAPair({ content: '', sources: [], pipeline_result: null });
  const resolvedPair = makeChatQAPair({ has_feedback: hasFeedback, is_liked: isLiked, is_saved: args.saved });
  const currentQA =
    args.state === 'request-error' ? undefined : args.state === 'resolved' ? resolvedPair : emptyAnswerPair;

  return (
    <div className="bg-fill-normal-normal flex min-h-180 items-start justify-center p-8">
      <div className="w-192.75 max-w-full">
        <RagAnswer
          currentQA={currentQA}
          sessionId="storybook-chat-session"
          isLoading={args.state === 'loading'}
          isError={args.state === 'request-error'}
          pipelineQueryType={args.state === 'loading' ? args.pipelineQueryType : null}
          pipelineReasoning={args.state === 'loading' ? args.pipelineReasoning : null}
          onRetry={args.onRetry}
          onFeedbackSubmitted={args.onFeedbackSubmitted}
        />
      </div>
    </div>
  );
}

const meta = {
  title: 'Compositions/Chat/Answers/RagAnswer',
  component: RagAnswer,
  tags: ['autodocs'],
  args: {
    state: 'resolved',
    feedbackState: 'unrated',
    saved: false,
    pipelineQueryType: 'complex',
    pipelineReasoning: '정책과 운영 대응 절차를 함께 확인하는 질문입니다.',
    onRetry: fn(),
    onFeedbackSubmitted: fn(),
  },
  argTypes: {
    state: { control: 'select', options: stateOptions },
    feedbackState: { control: 'select', options: feedbackStateOptions },
    saved: { control: 'boolean' },
    pipelineQueryType: { control: 'select', options: pipelineOptions },
    pipelineReasoning: { control: 'text' },
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
      states: ['resolved', 'loading', 'inline-error', 'request-error', 'liked', 'disliked', 'saved'],
      usedBy: ['chat'],
      dataNotes: ['Rich Markdown, citations, source fixtures, and pipeline events share one Chat domain fixture.'],
      interactionNotes: ['The resolved interaction opens both the process accordion and dislike feedback panel.'],
    }),
  },
} satisfies Meta<RagAnswerStoryArgs>;

export default meta;

type Story = StoryObj<RagAnswerStoryArgs>;

export const Playground: Story = {
  render: (args) => <RagAnswerSurface {...args} />,
};

export const ResolvedInteraction: Story = {
  render: (args) => <RagAnswerSurface {...args} />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const processTrigger = canvas.getByRole('button', { name: /질문과 연관된 6개의 핵심 자료/ });

    await userEvent.click(processTrigger);
    await waitFor(() => expect(canvas.getByText('탐색 계획 수립')).toBeVisible());

    await userEvent.click(canvas.getByRole('button', { name: '별로인 응답' }));
    const feedbackHeading = await canvas.findByText('답변이 마음에 들지 않은 이유가 무엇인가요?');
    await waitFor(() => expect(feedbackHeading).toBeVisible());
  },
};

export const LikedAndSaved: Story = {
  args: {
    feedbackState: 'liked',
    saved: true,
  },
  render: (args) => <RagAnswerSurface {...args} />,
};

export const Loading: Story = {
  args: { state: 'loading' },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'chat',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'loading',
      designSource: 'dev-preview',
      states: ['loading', 'pipeline-type'],
      usedBy: ['chat'],
    }),
  },
  render: (args) => <RagAnswerSurface {...args} />,
};

export const InlineError: Story = {
  args: { state: 'inline-error' },
  render: (args) => <RagAnswerSurface {...args} />,
};

export const RequestError: Story = {
  args: { state: 'request-error' },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'chat',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'error',
      designSource: 'dev-preview',
      states: ['request-error'],
      usedBy: ['chat'],
    }),
  },
  render: (args) => <RagAnswerSurface {...args} />,
};
