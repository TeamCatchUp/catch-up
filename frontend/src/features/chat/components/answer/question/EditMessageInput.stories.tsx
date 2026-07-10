'use client';

import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, within } from 'storybook/test';

import { chatQuestionFixture } from '@/features/chat/__fixtures__/chatStory.fixtures';

import { catchupParameters } from '../../../../../../.storybook/catchupStoryParameters';
import EditMessageInput from './EditMessageInput';

const meta = {
  title: 'Primitives/Chat/Questions/EditMessageInput',
  component: EditMessageInput,
  tags: ['autodocs'],
  args: {
    initialContent: chatQuestionFixture.content,
    onCancel: fn(),
    onSubmit: fn(async () => undefined),
  },
  argTypes: {
    initialContent: { control: 'text' },
    onCancel: { control: false },
    onSubmit: { control: false },
  },
  decorators: [
    (Story) => (
      <div className="bg-fill-normal-normal flex min-h-48 items-start justify-center p-6">
        <div className="w-160 max-w-full">
          <Story />
        </div>
      </div>
    ),
  ],
  parameters: {
    ...catchupParameters({
      level: 'primitive',
      domain: 'chat',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'realistic-fixture',
      designSource: 'dev-preview',
      states: ['default', 'focused', 'empty', 'submit', 'cancel'],
      usedBy: ['chat'],
      interactionNotes: ['Enter submits trimmed text and Escape cancels editing.'],
    }),
  },
} satisfies Meta<typeof EditMessageInput>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Playground: Story = {};

export const SubmitWithEnter: Story = {
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);
    const input = canvas.getByRole('textbox');

    await userEvent.clear(input);
    await userEvent.type(input, '재시도 횟수를 세 번으로 제한해도 될까요?{enter}');

    await expect(args.onSubmit).toHaveBeenCalledWith('재시도 횟수를 세 번으로 제한해도 될까요?');
  },
};

export const CancelWithEscape: Story = {
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);

    await userEvent.type(canvas.getByRole('textbox'), '{escape}');

    await expect(args.onCancel).toHaveBeenCalledOnce();
  },
};
