'use client';

import { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, userEvent, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../.storybook/catchupStoryParameters';
import FeedbackDetailInput from './FeedbackDetailInput';

interface FeedbackDetailInputStoryArgs {
  detailText: string;
  isSubmitting: boolean;
  entered: boolean;
  onSubmit: () => void;
  onCancel: () => void;
}

function FeedbackDetailInputSurface(args: FeedbackDetailInputStoryArgs) {
  const [detailText, setDetailText] = useState(args.detailText);

  return (
    <div className="bg-fill-normal-normal flex min-h-56 items-start justify-center p-6">
      <div className="w-193.25 max-w-full">
        <FeedbackDetailInput
          detailText={detailText}
          onDetailChange={setDetailText}
          onSubmit={args.onSubmit}
          onCancel={args.onCancel}
          isSubmitting={args.isSubmitting}
          entered={args.entered}
        />
      </div>
    </div>
  );
}

const meta = {
  title: 'Primitives/Chat/Feedback/FeedbackDetailInput',
  component: FeedbackDetailInput,
  tags: ['autodocs'],
  args: {
    detailText: '',
    isSubmitting: false,
    entered: true,
    onSubmit: fn(),
    onCancel: fn(),
  },
  argTypes: {
    detailText: { control: 'text' },
    isSubmitting: { control: 'boolean' },
    entered: { control: 'boolean' },
    onSubmit: { control: false },
    onCancel: { control: false },
  },
  parameters: {
    ...catchupParameters({
      level: 'primitive',
      domain: 'chat',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'dev-preview',
      states: ['empty', 'filled', 'submitting', 'entered', 'exiting'],
      usedBy: ['chat'],
      interactionNotes: ['Enter submits while Shift+Enter remains available for multiline feedback.'],
    }),
  },
} satisfies Meta<FeedbackDetailInputStoryArgs>;

export default meta;

type Story = StoryObj<FeedbackDetailInputStoryArgs>;

export const Playground: Story = {
  render: (args) => <FeedbackDetailInputSurface {...args} />,
};

export const SubmitWithEnter: Story = {
  render: (args) => <FeedbackDetailInputSurface {...args} />,
  play: async ({ args, canvasElement }) => {
    const canvas = within(canvasElement);
    const textarea = canvas.getByPlaceholderText('자세한 피드백을 남겨주세요.');

    await userEvent.type(textarea, '재시도 조건의 예외 사례도 함께 설명해주세요.');
    await userEvent.keyboard('{Enter}');

    await expect(args.onSubmit).toHaveBeenCalledOnce();
  },
};

export const Submitting: Story = {
  args: {
    detailText: '피드백을 제출하고 있습니다.',
    isSubmitting: true,
  },
  render: (args) => <FeedbackDetailInputSurface {...args} />,
};
