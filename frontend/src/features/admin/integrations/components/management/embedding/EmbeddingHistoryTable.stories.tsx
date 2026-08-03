import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../../.storybook/catchupStoryParameters';
import EmbeddingHistoryTable from './EmbeddingHistoryTable';

const ITEMS = [
  { id: 'f1', target: '채널명 A', status: 'failed' as const, executedAt: '2026.03.18 00:00 PM', failureCount: 10 },
  { id: 'f2', target: '채널명 B', status: 'failed' as const, executedAt: '2026.03.18 00:00 PM', failureCount: 123456 },
  { id: 's1', target: '채널명 C', status: 'success' as const, executedAt: '2026.03.18 00:00 PM' },
  { id: 's2', target: '채널명 D', status: 'success' as const, executedAt: '2026.03.18 00:00 PM' },
];

const meta = {
  title: 'Compositions/Admin/Integrations/Embedding/EmbeddingHistoryTable',
  component: EmbeddingHistoryTable,
  tags: ['autodocs'],
  args: { service: 'slack', items: ITEMS, onRetry: fn() },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'admin',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17071-112226',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17071:112226',
      },
      viewport: { width: 716, height: 560 },
      states: ['all', 'success-only', 'failed-only', 'empty'],
      dataNotes: [
        '필터 라벨은 현행과 같은 전체/성공/실패다.',
        '현행에 있던 건수 배지와 실패 빨간 점은 Figma 신규에 없어 뺐다 — 미결 #18.',
      ],
    }),
  },
} satisfies Meta<typeof EmbeddingHistoryTable>;

export default meta;

type Story = StoryObj<typeof EmbeddingHistoryTable>;

const Frame = ({ children }: { children: React.ReactNode }) => (
  <div className="bg-fill-normal-normal w-179 p-6">{children}</div>
);

export const All: Story = {
  render: (args) => (
    <Frame>
      <EmbeddingHistoryTable {...args} />
    </Frame>
  ),
  play: async ({ canvasElement, userEvent, args }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('임베딩 히스토리')).toBeInTheDocument();
    await expect(canvas.getByRole('tab', { name: '전체' })).toHaveAttribute('aria-selected', 'true');
    await expect(canvas.getAllByRole('row')).toHaveLength(5); // 헤더 1 + 본문 4

    await userEvent.click(canvas.getAllByRole('button', { name: '임베딩 재시도' })[0]);
    await expect(args.onRetry).toHaveBeenCalledWith('f1');
  },
};

export const SuccessOnly: Story = {
  render: (args) => (
    <Frame>
      <EmbeddingHistoryTable {...args} />
    </Frame>
  ),
  play: async ({ canvasElement, userEvent }) => {
    const canvas = within(canvasElement);

    await userEvent.click(canvas.getByRole('tab', { name: '성공' }));
    await expect(canvas.getAllByRole('row')).toHaveLength(3); // 헤더 1 + 성공 2
    // '실패'는 필터 탭 라벨과 겹치므로 재시도 버튼 유무로 본다
    await expect(canvas.queryByRole('button', { name: '임베딩 재시도' })).not.toBeInTheDocument();
  },
};

export const FailedOnly: Story = {
  render: (args) => (
    <Frame>
      <EmbeddingHistoryTable {...args} />
    </Frame>
  ),
  play: async ({ canvasElement, userEvent }) => {
    const canvas = within(canvasElement);

    await userEvent.click(canvas.getByRole('tab', { name: '실패' }));
    await expect(canvas.getAllByRole('row')).toHaveLength(3); // 헤더 1 + 실패 2
    await expect(canvas.getByText('50,000+건')).toBeInTheDocument();
  },
};

export const Empty: Story = {
  args: { items: [] },
  render: (args) => (
    <Frame>
      <EmbeddingHistoryTable {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    // 빈 상태 문구는 현행 코드에서 승계한다 — Figma에 근거가 없다
    await expect(canvas.getByText('임베딩 히스토리가 없습니다.')).toBeInTheDocument();
  },
};
