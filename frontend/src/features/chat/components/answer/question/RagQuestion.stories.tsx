'use client';

import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, waitFor, within } from 'storybook/test';

import { chatQuestionFixture, makeChatQAPair } from '@/features/chat/__fixtures__/chatStory.fixtures';

import { catchupParameters } from '../../../../../../.storybook/catchupStoryParameters';
import RagQuestion from './RagQuestion';

const meta = {
  title: 'Compositions/Chat/Questions/RagQuestion',
  component: RagQuestion,
  tags: ['autodocs'],
  args: {
    currentQA: makeChatQAPair(),
    isLastPage: true,
    onSubmitEdit: fn(async () => undefined),
  },
  argTypes: {
    currentQA: { control: 'object' },
    isLastPage: { control: 'boolean' },
    onSubmitEdit: { control: false },
  },
  decorators: [
    (Story) => (
      <div className="bg-fill-normal-normal flex min-h-48 items-start justify-center p-6">
        <div className="w-192.75 max-w-full">
          <Story />
        </div>
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
      states: ['default', 'hover-actions', 'editing', 'read-only'],
      usedBy: ['chat'],
      interactionNotes: ['The latest question can enter edit mode and submit updated content.'],
    }),
  },
} satisfies Meta<typeof RagQuestion>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Playground: Story = {};

export const EditLatestQuestion: Story = {
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);
    const editButton = canvas.getByRole('button', { name: '질문 수정하기' });

    await userEvent.tab();
    await expect(editButton).toHaveFocus();
    await waitFor(() => expect(editButton).toBeVisible());
    await userEvent.keyboard('{enter}');

    const input = canvas.getByRole('textbox');
    await userEvent.clear(input);
    await userEvent.type(input, '일시 오류 코드의 재시도 간격도 알려주세요.');
    await userEvent.click(canvas.getByRole('button', { name: '보내기' }));

    await waitFor(() =>
      expect(args.onSubmitEdit).toHaveBeenCalledWith(
        chatQuestionFixture.id,
        '일시 오류 코드의 재시도 간격도 알려주세요.',
      ),
    );
  },
};

export const PreviousQuestion: Story = {
  args: {
    isLastPage: false,
  },
};
