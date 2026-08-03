import type { Meta, StoryObj } from '@storybook/nextjs-vite';
import { expect, fn, within } from 'storybook/test';

import { catchupParameters } from '../../../../../../../../.storybook/catchupStoryParameters';
import ChannelTalkEmbeddingFooterBar from './ChannelTalkEmbeddingFooterBar';

const meta = {
  title: 'Compositions/Admin/Integrations/Channel Talk/ChannelTalkEmbeddingFooterBar',
  component: ChannelTalkEmbeddingFooterBar,
  tags: ['autodocs'],
  args: {
    channelCount: 5,
    documentCount: 18,
    allSelected: false,
    partiallySelected: true,
    onToggleAll: fn(),
    onEmbed: fn(),
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
        url: 'https://www.figma.com/design/7UwupbVvmHkElmP2OBJQio/Design-System?node-id=17414-97736',
        fileKey: '7UwupbVvmHkElmP2OBJQio',
        nodeId: '17414:97736',
      },
      viewport: { width: 780, height: 120 },
      states: ['partial', 'all', 'none'],
      layoutNotes: ['780×60, 위선만 있고 배경 없음. px 32 / py 12, gap 6.'],
      dataNotes: [
        '스텝 ①의 ChannelTalkFooterBar(17345:84633)와 다른 물건이다 — 저건 버튼 2개.',
        '집계는 숫자만 #3385FF로 강조된다.',
      ],
    }),
  },
} satisfies Meta<typeof ChannelTalkEmbeddingFooterBar>;

export default meta;

type Story = StoryObj<typeof ChannelTalkEmbeddingFooterBar>;

const Frame = ({ children }: { children: React.ReactNode }) => (
  <div className="bg-fill-normal-normal w-195">{children}</div>
);

export const Partial: Story = {
  render: (args) => (
    <Frame>
      <ChannelTalkEmbeddingFooterBar {...args} />
    </Frame>
  ),
  play: async ({ canvasElement, userEvent, args }) => {
    const canvas = within(canvasElement);
    const checkbox = canvas.getByRole('checkbox', { name: '전체 선택하기' });

    await expect(checkbox).toHaveAttribute('aria-checked', 'mixed');
    await expect(canvas.getByText('개 채널')).toBeInTheDocument();

    await userEvent.click(checkbox);
    await expect(args.onToggleAll).toHaveBeenCalled();

    await userEvent.click(canvas.getByRole('button', { name: '임베딩하기' }));
    await expect(args.onEmbed).toHaveBeenCalled();
  },
};

export const AllSelected: Story = {
  args: { allSelected: true, partiallySelected: false },
  render: (args) => (
    <Frame>
      <ChannelTalkEmbeddingFooterBar {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByRole('checkbox', { name: '전체 선택하기' })).toHaveAttribute('aria-checked', 'true');
  },
};

/** 하나도 안 고르면 임베딩할 대상이 없다 */
export const NoneSelected: Story = {
  args: { channelCount: 0, documentCount: 0, allSelected: false, partiallySelected: false },
  render: (args) => (
    <Frame>
      <ChannelTalkEmbeddingFooterBar {...args} />
    </Frame>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(canvas.getByRole('checkbox', { name: '전체 선택하기' })).toHaveAttribute('aria-checked', 'false');
    await expect(canvas.getByRole('button', { name: '임베딩하기' })).toBeDisabled();
  },
};
