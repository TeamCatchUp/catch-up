'use client';

import type { Meta, StoryObj } from '@storybook/nextjs-vite';

import { chatLoadingStepRows, makeChatQAPair } from '@/features/chat/__fixtures__/chatStory.fixtures';
import type { PipelineQueryType } from '@/features/chat/types';

import { catchupParameters } from '../../../../../.storybook/catchupStoryParameters';
import RagSidebar from './RagSidebar';

type RagSidebarState = 'resolved' | 'loading' | 'error' | 'empty';

interface RagSidebarStoryArgs {
  state: RagSidebarState;
  topic: string;
  pipelineQueryType: PipelineQueryType;
}

const stateOptions: readonly RagSidebarState[] = ['resolved', 'loading', 'error', 'empty'];
const pipelineOptions: readonly PipelineQueryType[] = ['simple', 'standard', 'complex'];

const resolvedPair = makeChatQAPair();
const emptyPair = makeChatQAPair({ id: 'chat-story-empty-answer', content: '', sources: [] });

function RagSidebarSurface(args: RagSidebarStoryArgs) {
  const isLoading = args.state === 'loading';
  const currentQA = args.state === 'empty' ? emptyPair : resolvedPair;

  return (
    <div className="bg-fill-normal-alternative flex h-200 min-w-300 justify-end overflow-hidden">
      <RagSidebar
        currentQA={currentQA}
        isLoading={isLoading}
        isError={args.state === 'error'}
        stepRows={isLoading ? chatLoadingStepRows : []}
        topic={isLoading ? args.topic : null}
        pipelineQueryType={isLoading ? args.pipelineQueryType : null}
        pipelineReasoning={isLoading ? '질문을 분석하고 관련 자료를 탐색합니다.' : null}
      />
    </div>
  );
}

const meta = {
  title: 'Screens/Chat/RagSidebar',
  component: RagSidebar,
  tags: ['autodocs'],
  args: {
    state: 'resolved',
    topic: '결제 승인 실패 재시도 정책',
    pipelineQueryType: 'standard',
  },
  argTypes: {
    state: {
      control: 'select',
      options: stateOptions,
    },
    topic: {
      control: 'text',
    },
    pipelineQueryType: {
      control: 'select',
      options: pipelineOptions,
    },
  },
  parameters: {
    ...catchupParameters({
      level: 'screen',
      domain: 'chat',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      designSource: 'dev-preview',
      states: ['resolved', 'pipeline-loading', 'error', 'empty'],
      usedBy: ['chat'],
      viewport: { width: 1280, height: 800 },
      layoutNotes: ['RagSidebar is desktop-only and becomes visible at the lg breakpoint.'],
      dataNotes: ['The resolved state shares the same source fixtures and citation ordering as SourceList.'],
      interactionNotes: ['Controls switch the full sidebar between answer, pipeline, error, and empty states.'],
    }),
  },
} satisfies Meta<RagSidebarStoryArgs>;

export default meta;

type Story = StoryObj<RagSidebarStoryArgs>;

export const Playground: Story = {
  render: (args) => <RagSidebarSurface {...args} />,
};

export const PipelineLoading: Story = {
  args: { state: 'loading' },
  parameters: {
    ...catchupParameters({
      level: 'screen',
      domain: 'chat',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'loading',
      designSource: 'dev-preview',
      states: ['pipeline-loading'],
      usedBy: ['chat'],
      viewport: { width: 1280, height: 800 },
    }),
  },
  render: (args) => <RagSidebarSurface {...args} />,
};

export const Error: Story = {
  args: { state: 'error' },
  parameters: {
    ...catchupParameters({
      level: 'screen',
      domain: 'chat',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'error',
      designSource: 'dev-preview',
      states: ['error'],
      usedBy: ['chat'],
      viewport: { width: 1280, height: 800 },
    }),
  },
  render: (args) => <RagSidebarSurface {...args} />,
};

export const Empty: Story = {
  args: { state: 'empty' },
  parameters: {
    ...catchupParameters({
      level: 'screen',
      domain: 'chat',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'empty',
      designSource: 'dev-preview',
      states: ['empty'],
      usedBy: ['chat'],
      viewport: { width: 1280, height: 800 },
    }),
  },
  render: (args) => <RagSidebarSurface {...args} />,
};
