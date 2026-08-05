import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../../.storybook/catchupStoryParameters';
import EmbeddingHistoryRow from './EmbeddingHistoryRow';

const meta = {
  title: 'Compositions/Admin/Integrations/Embedding/EmbeddingHistoryRow',
  component: EmbeddingHistoryRow,
  tags: ['autodocs'],
  args: {
    service: 'slack',
    target: '채널명 text text text text text texttexttexttexttext',
    status: 'running',
    executedAt: null,
    failureCount: 0,
    onRetry: fn(),
  },
  argTypes: {
    status: { control: 'inline-radio', options: ['running', 'success', 'failed'] },
  },
  parameters: {
    ...catchupParameters({
      level: 'composition',
      domain: 'admin',
      fsdLayer: 'features',
      owner: 'feature',
      dataProfile: 'static',
      designSource: 'figma',
      figma: {
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17413-33953',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17413:33953',
      },
      viewport: { width: 716, height: 100 },
      states: ['running', 'success', 'failed', 'failed-over-cap', 'failed-count-pending'],
      layoutNotes: [
        '4슬롯: 대상(fill) · 상태(150) · 시각(150) · 액션(32).',
        '진행중의 시각 칸은 텍스트가 아니라 회색 선이다.',
        '성공 행도 액션 슬롯을 비운 채 유지해 열 정렬을 맞춘다.',
      ],
    }),
  },
} satisfies Meta<typeof EmbeddingHistoryRow>;

export default meta;

type Story = StoryObj<typeof EmbeddingHistoryRow>;

/** tr이라 table/tbody 안에서만 유효하다 */
const Frame = ({ children }: { children: React.ReactNode }) => (
  <div className="bg-fill-normal-normal w-179 p-3">
    <table className="w-full table-fixed">
      <tbody>{children}</tbody>
    </table>
  </div>
);

export const Running: Story = {
  render: (args) => (
    <Frame>
      <EmbeddingHistoryRow {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('진행중')).toBeInTheDocument();
    // 진행중은 시각도 재시도 버튼도 없다
    await expect(canvas.queryByRole('button')).not.toBeInTheDocument();
  },
};

export const Success: Story = {
  args: { status: 'success', executedAt: '2026.03.18 00:00 PM' },
  render: (args) => (
    <Frame>
      <EmbeddingHistoryRow {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('성공')).toBeInTheDocument();
    await expect(canvas.getByText('2026.03.18 00:00 PM')).toBeInTheDocument();
    // 성공도 재시도 버튼은 없다 — 슬롯만 비워 정렬을 맞춘다
    await expect(canvas.queryByRole('button')).not.toBeInTheDocument();
  },
};

export const Failed: Story = {
  args: { status: 'failed', executedAt: '2026.03.18 00:00 PM', failureCount: 10 },
  render: (args) => (
    <Frame>
      <EmbeddingHistoryRow {...args} />
    </Frame>
  ),
  play: async ({ canvasElement, userEvent, args }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('실패')).toBeInTheDocument();
    await expect(canvas.getByText('10건')).toBeInTheDocument();

    await userEvent.click(canvas.getByRole('button', { name: '임베딩 재시도' }));
    await expect(args.onRetry).toHaveBeenCalled();
  },
};

/** 실패 건수 미확정 — gap 조회가 로딩 중이거나 실패하면 0건 대신 대시를 그린다 */
export const FailedCountPending: Story = {
  args: { status: 'failed', executedAt: '2026.03.18 00:00 PM', failureCount: undefined },
  render: (args) => (
    <Frame>
      <EmbeddingHistoryRow {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText('실패')).toBeInTheDocument();
    // 유효한 0과 구분 — "0건"이 아니라 "-"
    await expect(canvas.queryByText('0건')).not.toBeInTheDocument();
    await expect(canvas.getByText('-')).toBeInTheDocument();
  },
};

/** 5만을 넘으면 건수를 접는다 */
export const FailedOverCap: Story = {
  args: { status: 'failed', executedAt: '2026.03.18 00:00 PM', failureCount: 123456 },
  render: (args) => (
    <Frame>
      <EmbeddingHistoryRow {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText('50,000+건')).toBeInTheDocument();
  },
};
