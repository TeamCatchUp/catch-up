'use client';

import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, userEvent, waitFor, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../.storybook/catchupStoryParameters';
import CollapsibleQuestionText from './CollapsibleQuestionText';

const longQuestion =
  '결제 승인 실패가 발생했을 때 오류 코드별로 재시도를 허용하는 조건과 최대 횟수, 재시도 간격, 고객 안내 시점, 운영 채널 알림 기준까지 한 번에 정리해주세요. 특히 일시 오류와 영구 오류를 구분해서 설명해주세요.';

const meta = {
  title: 'Primitives/Chat/Questions/CollapsibleQuestionText',
  component: CollapsibleQuestionText,
  tags: ['autodocs'],
  args: {
    content: longQuestion,
  },
  argTypes: {
    content: { control: 'text' },
  },
  decorators: [
    (Story) => (
      <div className="bg-fill-normal-normal flex min-h-48 items-start justify-center p-6">
        <div className="relative w-160 max-w-full">
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
      states: ['short', 'collapsed', 'expanded'],
      usedBy: ['chat'],
      interactionNotes: ['Long questions toggle between two-line and expanded states.'],
    }),
  },
} satisfies Meta<typeof CollapsibleQuestionText>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Playground: Story = {};

export const ShortQuestion: Story = {
  args: {
    content: '결제 승인 실패의 재시도 기준을 알려주세요.',
  },
};

export const ExpandAndCollapse: Story = {
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    const trigger = await waitFor(() => canvas.getByRole('button', { name: '질문 펼치기' }));

    await userEvent.click(trigger);
    await expect(trigger).toHaveAttribute('aria-expanded', 'true');
    await expect(trigger).toHaveAccessibleName('질문 접기');

    await userEvent.click(trigger);
    await expect(trigger).toHaveAttribute('aria-expanded', 'false');
  },
};
