'use client';

import { useCallback, useState } from 'react';
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, waitFor, within } from 'storybook/test';

import {
  chatConversationMessagesFixture,
  chatConversationStreamingMessagesFixture,
  chatLoadingStepRows,
  chatSourceFixtures,
  chatStorySessionId,
} from '@/features/chat/__fixtures__/chatStory.fixtures';
import { chatScreenHandlers } from '@/features/chat/__fixtures__/chatStory.handlers';
import RagQuestion from '@/features/chat/components/answer/question/RagQuestion';
import RagAnswer from '@/features/chat/components/answer/RagAnswer';
import DateDivider from '@/features/chat/components/DateDivider';
import RagContentHeader from '@/features/chat/components/header/RagContentHeader';
import RagInput from '@/features/chat/components/RagInput';
import ScrollToBottomButton from '@/features/chat/components/ScrollToBottomButton';
import RagSidebar from '@/features/chat/components/sidebar/RagSidebar';
import useRagFilters from '@/features/chat/hooks/filter/useRagFilters';
import useRagScroll from '@/features/chat/hooks/scroll/useRagScroll';
import type { DocsSource } from '@/shared/types/source';

import { catchupParameters } from '../../../../.storybook/catchupStoryParameters';

type ChatConversationState = 'resolved' | 'loading' | 'request-error';

interface ChatConversationStoryArgs {
  state: ChatConversationState;
  initialSources: DocsSource[];
  onSubmitEdit: (messageId: string, newContent: string) => Promise<void>;
  onFeedbackSubmitted: (messageId: string, isLiked: boolean | undefined) => void;
  onSendMessage: (message: string) => Promise<void>;
  onStop: () => void;
}

const stateOptions: readonly ChatConversationState[] = ['resolved', 'loading', 'request-error'];
const sourceOptions: readonly DocsSource[] = ['confluence', 'jira', 'slack', 'github', 'channel_talk'];

function ChatConversationSurface(args: ChatConversationStoryArgs) {
  const isLoading = args.state === 'loading';
  const isError = args.state === 'request-error';
  const messages = isLoading || isError ? chatConversationStreamingMessagesFixture : chatConversationMessagesFixture;
  const filters = useRagFilters({ initialSources: args.initialSources });
  const { qaPairs, qaRefs, scrollContainerCallbackRef, scrollContainerHeight, scrollToLatest, activePairIndex } =
    useRagScroll({
      messages,
      scrollToLatestOnGeneration: isLoading,
    });
  const [scrollContainer, setScrollContainer] = useState<HTMLDivElement | null>(null);
  const combinedScrollContainerRef = useCallback(
    (node: HTMLDivElement | null) => {
      scrollContainerCallbackRef(node);
      setScrollContainer(node);
    },
    [scrollContainerCallbackRef],
  );
  const currentSidebarQA = isLoading
    ? qaPairs[qaPairs.length - 1]
    : (qaPairs[activePairIndex] ?? qaPairs[qaPairs.length - 1]);

  return (
    <div className="bg-fill-normal-normal flex h-screen w-full flex-col overflow-hidden">
      <RagContentHeader title="결제 승인 실패 대응 정책" sessionId={chatStorySessionId} />
      <div className="flex min-h-0 flex-1">
        <div className="bg-fill-normal-normal flex min-w-0 flex-1 flex-col overflow-hidden">
          <div className="border-line-normal-neutral relative flex min-h-0 flex-1 flex-col overflow-hidden border-r-0">
            <div
              ref={combinedScrollContainerRef}
              data-chat-scroll-container
              className="custom-scrollbar flex min-h-0 flex-1 flex-col items-center overflow-y-auto scroll-smooth px-16 pt-3 pb-9"
            >
              <DateDivider className="mb-8 w-full max-w-203" date={new Date('2026-07-09T06:00:00.000Z')} />
              <div className="mx-auto flex w-full max-w-203 flex-1 flex-col gap-12">
                {qaPairs.map((qaPair, index) => {
                  const isLastPair = index === qaPairs.length - 1;

                  return (
                    <div
                      key={qaPair.question.id}
                      ref={(element) => {
                        qaRefs.current.set(index, element);
                        element?.setAttribute('data-qa-index', String(index));
                      }}
                      className="flex flex-col gap-6"
                      style={{ minHeight: scrollContainerHeight }}
                    >
                      <RagQuestion currentQA={qaPair} isLastPage={isLastPair} onSubmitEdit={args.onSubmitEdit} />
                      <RagAnswer
                        currentQA={qaPair}
                        sessionId={chatStorySessionId}
                        isLoading={isLoading && isLastPair}
                        isError={isError && isLastPair}
                        pipelineQueryType={isLoading && isLastPair ? 'standard' : null}
                        pipelineReasoning={
                          isLoading && isLastPair ? '정책과 최근 팀 논의를 함께 확인하고 있습니다.' : null
                        }
                        onFeedbackSubmitted={args.onFeedbackSubmitted}
                        onRetry={args.onSubmitEdit}
                      />
                    </div>
                  );
                })}
              </div>
            </div>
            <ScrollToBottomButton container={scrollContainer} />
          </div>
          <RagInput
            filters={filters}
            isLoading={isLoading}
            onSendMessage={args.onSendMessage}
            onStop={args.onStop}
            onNewMessage={scrollToLatest}
          />
        </div>
        <RagSidebar
          currentQA={currentSidebarQA}
          isLoading={isLoading}
          isError={isError}
          stepRows={isLoading ? chatLoadingStepRows : []}
          topic={isLoading ? '결제 승인 실패 재시도 정책' : null}
          pipelineQueryType={isLoading ? 'standard' : null}
          pipelineReasoning={isLoading ? '질문을 분석하고 관련 자료를 탐색합니다.' : null}
        />
      </div>
    </div>
  );
}

const meta = {
  title: 'Screens/Chat/Conversation',
  component: ChatConversationSurface,
  tags: ['autodocs'],
  args: {
    state: 'resolved',
    initialSources: [],
    onSubmitEdit: fn(async () => undefined),
    onFeedbackSubmitted: fn(),
    onSendMessage: fn(async () => undefined),
    onStop: fn(),
  },
  argTypes: {
    state: { control: 'select', options: stateOptions },
    initialSources: { control: 'check', options: sourceOptions },
    onSubmitEdit: { control: false },
    onFeedbackSubmitted: { control: false },
    onSendMessage: { control: false },
    onStop: { control: false },
  },
  parameters: {
    layout: 'fullscreen',
    msw: { handlers: chatScreenHandlers },
    ...catchupParameters({
      level: 'screen',
      domain: 'chat',
      fsdLayer: 'app',
      owner: 'app',
      dataProfile: 'msw',
      designSource: 'dev-preview',
      states: ['resolved', 'sidebar-synced', 'pipeline-loading', 'request-error', 'filtered-input'],
      usedBy: ['chat'],
      viewport: { width: 1440, height: 900 },
      layoutNotes: [
        'The story mirrors the App Router screen composition while route loading and network hooks remain outside Storybook.',
        'Each QA pair reserves one scroll viewport so the real useRagScroll observer can drive sidebar synchronization.',
      ],
      dataNotes: ['Questions, answers, citations, pipeline rows, and MSW actions share the Chat domain fixture.'],
      interactionNotes: [
        'Scrolling from the previous QA to the latest QA updates the source sidebar through useRagScroll.',
      ],
    }),
  },
  render: (args) => <ChatConversationSurface {...args} />,
} satisfies Meta<ChatConversationStoryArgs>;

export default meta;

type Story = StoryObj<ChatConversationStoryArgs>;

export const Playground: Story = {};

export const SidebarSync: Story = {
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const scrollContainer = canvasElement.querySelector('[data-chat-scroll-container]');

    if (!(scrollContainer instanceof HTMLDivElement)) {
      throw new Error('Chat 스크롤 컨테이너를 찾을 수 없습니다.');
    }

    await waitFor(() => expect(canvas.getByText(chatSourceFixtures.confluence.title)).toBeVisible());
    await expect(canvas.queryByText(chatSourceFixtures.jira.title)).not.toBeInTheDocument();

    scrollContainer.scrollTop = scrollContainer.scrollHeight;
    scrollContainer.dispatchEvent(new Event('scroll'));

    await waitFor(() => expect(canvas.getByText(chatSourceFixtures.jira.title)).toBeVisible(), { timeout: 3000 });
  },
};

export const PipelineLoading: Story = {
  args: {
    state: 'loading',
    initialSources: ['jira', 'slack'],
  },
  parameters: {
    ...catchupParameters({
      level: 'screen',
      domain: 'chat',
      fsdLayer: 'app',
      owner: 'app',
      dataProfile: 'loading',
      designSource: 'dev-preview',
      states: ['pipeline-loading', 'filtered-input'],
      usedBy: ['chat'],
      viewport: { width: 1440, height: 900 },
    }),
  },
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);

    await userEvent.click(canvas.getByRole('button', { name: '답변 생성 중지' }));
    await expect(args.onStop).toHaveBeenCalledOnce();
  },
};

export const RequestError: Story = {
  args: {
    state: 'request-error',
  },
  parameters: {
    ...catchupParameters({
      level: 'screen',
      domain: 'chat',
      fsdLayer: 'app',
      owner: 'app',
      dataProfile: 'error',
      designSource: 'dev-preview',
      states: ['request-error'],
      usedBy: ['chat'],
      viewport: { width: 1440, height: 900 },
    }),
  },
};
