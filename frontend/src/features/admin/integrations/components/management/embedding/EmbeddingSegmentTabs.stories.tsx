import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../../.storybook/catchupStoryParameters';
import EmbeddingSegmentTabs from './EmbeddingSegmentTabs';

const meta = {
  title: 'Compositions/Admin/Integrations/EmbeddingSegmentTabs',
  component: EmbeddingSegmentTabs,
  tags: ['autodocs'],
  args: { value: 'manage', hasRunning: false, onChange: fn() },
  argTypes: {
    value: { control: 'inline-radio', options: ['manage', 'status'] },
    hasRunning: { control: 'boolean' },
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
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17071-111935',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17071:111935',
      },
      viewport: { width: 716, height: 120 },
      states: ['manage-selected', 'status-selected', 'running-dot'],
      tokenNotes: [
        '진행중 점 #3385FF는 bg-* 시맨틱이 없어 text-icon-primary-assistive + bg-current로 낸다.',
        'fill-primary는 blue-45(#1A75FF)라 한 칸 다르다.',
      ],
      layoutNotes: ['컨테이너 716×44 padding 4 gap 4, 버튼 각 352×36.'],
    }),
  },
} satisfies Meta<typeof EmbeddingSegmentTabs>;

export default meta;

type Story = StoryObj<typeof EmbeddingSegmentTabs>;

const Frame = ({ children }: { children: React.ReactNode }) => (
  <div className="bg-fill-normal-normal w-179 p-6">{children}</div>
);

export const ManageSelected: Story = {
  render: (args) => (
    <Frame>
      <EmbeddingSegmentTabs {...args} />
    </Frame>
  ),
  play: async ({ canvasElement, userEvent, args }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByRole('tab', { name: '임베딩 관리' })).toHaveAttribute('aria-selected', 'true');
    await expect(canvas.getByRole('tab', { name: /임베딩 현황/ })).toHaveAttribute('aria-selected', 'false');

    await userEvent.click(canvas.getByRole('tab', { name: /임베딩 현황/ }));
    await expect(args.onChange).toHaveBeenCalledWith('status');
  },
};

export const StatusSelected: Story = {
  args: { value: 'status' },
  render: (args) => (
    <Frame>
      <EmbeddingSegmentTabs {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByRole('tab', { name: /임베딩 현황/ })).toHaveAttribute('aria-selected', 'true');
  },
};

/** 진행중 작업이 있으면 현황 탭에 점이 붙는다 */
export const RunningDot: Story = {
  args: { hasRunning: true },
  render: (args) => (
    <Frame>
      <EmbeddingSegmentTabs {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    // 점은 장식이 아니라 상태 신호라 텍스트로도 읽혀야 한다
    await expect(canvas.getByRole('tab', { name: /임베딩 현황.*진행 중/ })).toBeInTheDocument();
  },
};
