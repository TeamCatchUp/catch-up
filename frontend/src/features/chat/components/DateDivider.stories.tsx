import type { Meta, StoryObj } from '@storybook/nextjs-vite';

import { catchupParameters } from '../../../../.storybook/catchupStoryParameters';
import DateDivider from './DateDivider';

const meta = {
  title: 'Primitives/Chat/Conversation/DateDivider',
  component: DateDivider,
  tags: ['autodocs'],
  args: {
    date: new Date(2026, 6, 10),
  },
  argTypes: {
    date: { control: 'date' },
    formatDate: { control: false },
  },
  decorators: [
    (Story) => (
      <div className="bg-fill-normal-normal p-6">
        <Story />
      </div>
    ),
  ],
  parameters: {
    ...catchupParameters({
      level: 'primitive',
      domain: 'chat',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'dev-preview',
      states: ['default', 'custom-format'],
      usedBy: ['chat'],
    }),
  },
} satisfies Meta<typeof DateDivider>;

export default meta;

type Story = StoryObj<typeof meta>;

export const Playground: Story = {};

export const CustomFormat: Story = {
  args: {
    formatDate: (date) => `${date.getFullYear()}년 ${date.getMonth() + 1}월 ${date.getDate()}일`,
  },
};
