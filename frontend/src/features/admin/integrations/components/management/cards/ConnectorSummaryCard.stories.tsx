import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../../.storybook/catchupStoryParameters';
import ConnectorSummaryCard from './ConnectorSummaryCard';

const meta = {
  title: 'Compositions/Admin/Integrations/Embedding/ConnectorSummaryCard',
  component: ConnectorSummaryCard,
  tags: ['autodocs'],
  args: { connected: true, dataRange: '2000.00.00 - 2000.00.00' },
  argTypes: {
    connected: { control: 'boolean' },
    dataRange: { control: 'text' },
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
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17071-111589',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17071:111589',
      },
      viewport: { width: 716, height: 160 },
      states: ['connected', 'disconnected', 'no-range'],
      reuseNotes: [
        '구 레이아웃의 카드 2개(ConnectionStatusCard + DataRangeCard)를 대체했고 그 둘은 삭제됐다.',
        '구 카드의 "보안 관련 설명 / 원문 보기" 행은 신규 디자인에 없다.',
      ],
      dataNotes: ['미연동·범위 없음 문구는 Figma에 없어 현행 코드에서 승계했다.'],
      tokenNotes: [
        '카드 배경 #F7F7F8 = bg-fill-normal-strong. 테두리만 있는 게 아니라 채워진 카드다.',
        '연동됨 #3385FF = text-text-primary-assistive, 날짜 #6D7882 = text-text-normal-alternative.',
      ],
    }),
  },
} satisfies Meta<typeof ConnectorSummaryCard>;

export default meta;

type Story = StoryObj<typeof ConnectorSummaryCard>;

const Frame = ({ children }: { children: React.ReactNode }) => (
  <div className="bg-fill-normal-normal w-179 p-6">{children}</div>
);

export const Connected: Story = {
  render: (args) => (
    <Frame>
      <ConnectorSummaryCard {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('연동 상태')).toBeInTheDocument();
    await expect(canvas.getByText('연동됨')).toBeInTheDocument();
    await expect(canvas.getByText('임베딩 데이터 범위')).toBeInTheDocument();
    await expect(canvas.getByText('2000.00.00 - 2000.00.00')).toBeInTheDocument();

    // 구 카드에 있던 행은 사라졌다
    await expect(canvas.queryByText('보안 관련 설명')).not.toBeInTheDocument();
    await expect(canvas.queryByText(/원문 보기/)).not.toBeInTheDocument();
  },
};

export const Disconnected: Story = {
  args: { connected: false, dataRange: null },
  render: (args) => (
    <Frame>
      <ConnectorSummaryCard {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText('연동 안됨')).toBeInTheDocument();
    await expect(canvas.getByText('연동되지 않았습니다.')).toBeInTheDocument();
  },
};

export const NoRange: Story = {
  args: { connected: true, dataRange: null },
  render: (args) => (
    <Frame>
      <ConnectorSummaryCard {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText('연동됨')).toBeInTheDocument();
    await expect(canvas.getByText('연동되지 않았습니다.')).toBeInTheDocument();
  },
};
