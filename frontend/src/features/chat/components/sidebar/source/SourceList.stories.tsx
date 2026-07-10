'use client';

import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, userEvent, within } from 'storybook/test';

import { chatAnswerWithCitations, chatSourceListFixture } from '@/features/chat/__fixtures__/chatStory.fixtures';

import { catchupParameters } from '../../../../../../.storybook/catchupStoryParameters';
import SourceList from './SourceList';

type SourceListState = 'resolved' | 'loading' | 'error' | 'empty';

interface SourceListStoryArgs {
  state: SourceListState;
  prefersReducedMotion: boolean;
}

const stateOptions: readonly SourceListState[] = ['resolved', 'loading', 'error', 'empty'];

function SourceListSurface(args: SourceListStoryArgs) {
  const isResolved = args.state === 'resolved';

  return (
    <div className="bg-fill-normal-normal border-line-normal-neutral flex h-180 w-108.75 max-w-full overflow-hidden border">
      <SourceList
        sources={isResolved ? chatSourceListFixture : []}
        answerContent={isResolved ? chatAnswerWithCitations : ''}
        isLoading={args.state === 'loading'}
        isError={args.state === 'error'}
        transitionKey={args.state}
        prefersReducedMotion={args.prefersReducedMotion}
      />
    </div>
  );
}

const meta = {
  title: 'Compositions/Chat/Sources/SourceList',
  component: SourceList,
  tags: ['autodocs'],
  args: {
    state: 'resolved',
    prefersReducedMotion: true,
  },
  argTypes: {
    state: {
      control: 'select',
      options: stateOptions,
    },
    prefersReducedMotion: {
      control: 'boolean',
    },
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'chat',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      designSource: 'dev-preview',
      states: ['resolved', 'filtered', 'loading', 'error', 'empty', 'reduced-motion'],
      usedBy: ['chat'],
      viewport: { width: 436, height: 720 },
      dataNotes: ['Cited sources follow answer citation order; non-cited sources render as recommendations.'],
      interactionNotes: ['The resolved story filters cards by integration and verifies the resulting content.'],
    }),
  },
} satisfies Meta<SourceListStoryArgs>;

export default meta;

type Story = StoryObj<SourceListStoryArgs>;

export const Playground: Story = {
  render: (args) => <SourceListSurface {...args} />,
};

export const FilterInteraction: Story = {
  args: {
    state: 'resolved',
  },
  render: (args) => <SourceListSurface {...args} />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await userEvent.click(canvas.getByRole('button', { name: /^Slack 1$/ }));

    await expect(
      canvas.getByText('"재시도는 승인 실패 코드가 일시 오류인 경우에만 허용하기로 했습니다."'),
    ).toBeVisible();
    await expect(canvas.queryByText('결제 승인 실패 시 재시도 정책 정리')).not.toBeInTheDocument();
  },
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
      states: ['loading'],
      usedBy: ['chat'],
    }),
  },
  render: (args) => <SourceListSurface {...args} />,
};

export const Error: Story = {
  args: { state: 'error' },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'chat',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'error',
      designSource: 'dev-preview',
      states: ['error'],
      usedBy: ['chat'],
    }),
  },
  render: (args) => <SourceListSurface {...args} />,
};

export const Empty: Story = {
  args: { state: 'empty' },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'chat',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'empty',
      designSource: 'dev-preview',
      states: ['empty'],
      usedBy: ['chat'],
    }),
  },
  render: (args) => <SourceListSurface {...args} />,
};
