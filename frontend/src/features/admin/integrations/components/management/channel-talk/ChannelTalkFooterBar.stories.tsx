import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../../.storybook/catchupStoryParameters';
import ChannelTalkFooterBar from './ChannelTalkFooterBar';

const meta = {
  title: 'Compositions/Admin/Integrations/Channel Talk/ChannelTalkFooterBar',
  component: ChannelTalkFooterBar,
  tags: ['autodocs'],
  args: { channelCount: 5, documentCount: 18, onAddChannel: fn(), onProceed: fn() },
  argTypes: {
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
      states: ['default', 'zero'],
      dataNotes: [
        '집계 문구는 "N개 채널 · M개 도큐먼트 연결됨" — 가운데 4x4 점 구분자.',
        '실패 건수의 50,000+ 규칙은 여기 적용하지 않는다(사용자 결정).',
        '임베딩하기에 활성 조건이 없다(사용자 결정) — 채널 0개여도 누를 수 있다.',
      ],
    }),
  },
} satisfies Meta<typeof ChannelTalkFooterBar>;

export default meta;

type Story = StoryObj<typeof ChannelTalkFooterBar>;

const Frame = ({ children }: { children: React.ReactNode }) => (
  <div className="bg-fill-normal-normal w-195">{children}</div>
);

/** 숫자만 색이 달라 텍스트 노드가 쪼개진다 — p 요소의 textContent로 본다 */
const byLine = (text: string) => (_content: string, el: Element | null) =>
  el?.tagName === 'P' && el.textContent === text;

export const Default: Story = {
  render: (args) => (
    <Frame>
      <ChannelTalkFooterBar {...args} />
    </Frame>
  ),
  play: async ({ canvasElement, userEvent, args }) => {
    const canvas = within(canvasElement);

    await expect(canvas.getByText(byLine('5개 채널'))).toBeInTheDocument();
    await expect(canvas.getByText(byLine('18개 도큐먼트 연결됨'))).toBeInTheDocument();

    await userEvent.click(canvas.getByRole('button', { name: /채널 추가/ }));
    await expect(args.onAddChannel).toHaveBeenCalled();

    await userEvent.click(canvas.getByRole('button', { name: /임베딩하기/ }));
    await expect(args.onProceed).toHaveBeenCalled();
  },
};

/** 채널이 없어도 임베딩하기는 막지 않는다 — 활성 조건이 없다(사용자 결정) */
export const Zero: Story = {
  args: { channelCount: 0, documentCount: 0 },
  render: (args) => (
    <Frame>
      <ChannelTalkFooterBar {...args} />
    </Frame>
  ),
  play: async ({ canvasElement, args, userEvent }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByText(byLine('0개 채널'))).toBeInTheDocument();
    await expect(canvas.getByText(byLine('0개 도큐먼트 연결됨'))).toBeInTheDocument();

    await expect(canvas.getByRole('button', { name: /임베딩하기/ })).toBeEnabled();
    await userEvent.click(canvas.getByRole('button', { name: /임베딩하기/ }));
    await expect(args.onProceed).toHaveBeenCalled();
  },
};
