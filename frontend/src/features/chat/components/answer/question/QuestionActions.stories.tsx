'use client';

import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, within } from 'storybook/test';

import { chatQuestionFixture } from '@/features/chat/__fixtures__/chatStory.fixtures';

import { catchupParameters } from '../../../../../../.storybook/catchupStoryParameters';
import QuestionActions from './QuestionActions';

const meta = {
  title: 'Compositions/Chat/Questions/QuestionActions',
  component: QuestionActions,
  tags: ['autodocs'],
  args: {
    content: chatQuestionFixture.content,
    onEdit: fn(),
  },
  argTypes: {
    content: { control: 'text' },
    onEdit: { control: false },
  },
  decorators: [
    (Story) => (
      <div className="bg-fill-normal-normal flex min-h-24 items-center justify-center p-6">
        <Story />
      </div>
    ),
  ],
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'chat',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      designSource: 'dev-preview',
      states: ['editable', 'copy-only'],
      usedBy: ['chat'],
      interactionNotes: ['Edit is surfaced as an action callback; copy reports through the global toast.'],
    }),
  },
} satisfies Meta<typeof QuestionActions>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Playground: Story = {};

export const EditAction: Story = {
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);

    await userEvent.click(canvas.getByRole('button', { name: '질문 수정하기' }));

    await expect(args.onEdit).toHaveBeenCalledOnce();
  },
};

export const CopyOnly: Story = {
  args: {
    onEdit: undefined,
  },
};
