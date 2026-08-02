import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../../.storybook/catchupStoryParameters';
import ChannelTalkFooterBar from './ChannelTalkFooterBar';

const meta = {
  title: 'Compositions/Admin/Integrations/ChannelTalkFooterBar',
  component: ChannelTalkFooterBar,
  tags: ['autodocs'],
  args: { channelCount: 5, documentCount: 18, canProceed: false, onAddChannel: fn(), onProceed: fn() },
  argTypes: {
    canProceed: { control: 'boolean' },
    channelCount: { control: 'number' },
    documentCount: { control: 'number' },
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
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17363-100408',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17363:100408',
      },
      viewport: { width: 780, height: 100 },
      states: ['disabled', 'enabled', 'zero'],
      dataNotes: [
        '집계 문구는 "N개 채널 · M개 도큐먼트 연결됨" — 가운데 4x4 점 구분자.',
        '실패 건수의 50,000+ 규칙은 여기 적용하지 않는다(사용자 결정).',
      ],
    }),
  },
} satisfies Meta<typeof ChannelTalkFooterBar>;

export default meta;

type Story = StoryObj<typeof ChannelTalkFooterBar>;

const Frame = ({ children }: { children: React.ReactNode }) => (
  <div className="bg-fill-normal-normal w-195">{children}</div>
);

export const Disabled: Story = {
  render: (args) => (
    <Frame>
      <ChannelTalkFooterBar {...args} />
    </Frame>
  ),
  play: async ({ canvasElement, userEvent, args }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText('5개 채널')).toBeInTheDocument();
    await expect(canvas.getByText('18개 도큐먼트 연결됨')).toBeInTheDocument();
    await expect(canvas.getByRole('button', { name: /임베딩하기/ })).toBeDisabled();

    await userEvent.click(canvas.getByRole('button', { name: /채널 추가/ }));
    await expect(args.onAddChannel).toHaveBeenCalled();
  },
};

export const Enabled: Story = {
  args: { canProceed: true },
  render: (args) => (
    <Frame>
      <ChannelTalkFooterBar {...args} />
    </Frame>
  ),
  play: async ({ canvasElement, userEvent, args }) => {
    const canvas = within(canvasElement);
    await userEvent.click(canvas.getByRole('button', { name: /임베딩하기/ }));
    await expect(args.onProceed).toHaveBeenCalled();
  },
};

export const Zero: Story = {
  args: { channelCount: 0, documentCount: 0 },
  render: (args) => (
    <Frame>
      <ChannelTalkFooterBar {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText('0개 채널')).toBeInTheDocument();
    await expect(canvas.getByText('0개 도큐먼트 연결됨')).toBeInTheDocument();
  },
};
